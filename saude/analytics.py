"""Indicadores calculados sobre registros locais, com filtros reproduzíveis."""
import csv
import io
from collections import Counter, defaultdict
from datetime import date, timedelta

from flask import Response, g, jsonify, request
from .catalog import can_access

from .db import audit, db, record_dict


def register(app, error, roles):
    @app.get("/api/analytics")
    @roles("gestor", "vigilancia")
    def analytics():
        today = date.today()
        try:
            start = date.fromisoformat(request.args.get("start", (today - timedelta(days=29)).isoformat()))
            end = date.fromisoformat(request.args.get("end", today.isoformat()))
            if end < start or (end - start).days > 3660:
                raise ValueError()
        except ValueError:
            raise error("Informe um período válido, de até dez anos.")
        unit = request.args.get("unit", "")
        all_rows = [record_dict(r) for r in db().execute("SELECT * FROM records") if can_access(g.user["role"], r["module"])]
        scoped = [r for r in all_rows if not unit or str(r.get("unit_id")) == unit]
        rows = [r for r in scoped if start.isoformat() <= r.get("date", r["created_at"][:10]) <= end.isoformat()]
        modules = defaultdict(list)
        for r in rows:
            modules[r["module"]].append(r)
        appointments = modules["appointments"]
        closed = [r for r in appointments if r["status"] in ("Concluído", "Faltou")]
        waiting = [r for r in scoped if r["module"] == "regulation" and r["status"] in ("Aguardando", "Em análise") and r["date"] <= end.isoformat()]
        waits = [(end - date.fromisoformat(r["date"])).days for r in waiting]
        summary = dict(
            completed=sum(r["status"] == "Concluído" for r in appointments),
            absence_rate=round(100 * sum(r["status"] == "Faltou" for r in closed) / len(closed), 2) if closed else None,
            waiting=len(waiting), average_wait_days=round(sum(waits) / len(waits), 1) if waits else None,
            billing_approved=round(sum(r["quantity"] * r["value"] for r in modules["billing"] if r["status"] == "Conferido"), 2),
            billing_rejected=sum(r["status"] == "Rejeitado" for r in modules["billing"]),
            transport_cost=round(sum(r.get("total_cost", 0) for r in modules["transport"] if r["status"] != "Cancelado"), 2),
            fleet_cost=round(sum(r["cost"] for r in modules["fleet_events"]), 2),
        )
        dimensions = {}
        for dimension in ("module", "unit_id", "status", "care_type", "month"):
            counts = Counter((r.get("date", r["created_at"][:10])[:7] if dimension == "month" else str(r.get(dimension) or "Não informado")) for r in rows)
            dimensions[dimension] = [dict(label=k, count=v) for k, v in sorted(counts.items())]
        bases = {}
        for r in all_rows:
            if r["module"] == "territories" and r["status"] == "Ativo" and r["date"] <= end.isoformat():
                key = r["territory"].casefold()
                if key not in bases or r["date"] > bases[key]["date"]:
                    bases[key] = r
        groups = defaultdict(list)
        for r in modules["surveillance"]:
            groups[(r["territory"], r["condition"])].append(r)
        epidemiology = []
        for (territory, condition), group in sorted(groups.items()):
            confirmed = len({r["patient_id"] for r in group if r["classification"] == "Confirmado"})
            base = bases.get(territory.casefold())
            # Denominador territorial só se aplica à rede inteira, sem recorte por unidade.
            rate = round(confirmed / base["population"] * 100000, 2) if base and not unit else None
            epidemiology.append(dict(territory=territory, condition=condition, notifications=len(group), confirmed_patients=confirmed, suspected=sum(r["classification"] == "Suspeito" for r in group), deaths=len({r["patient_id"] for r in group if r.get("outcome") == "Óbito"}), population=base["population"] if base else None, source=base["source"] if base else None, rate_per_100k=rate))
        goal_results = []
        mapping = {"Atendimentos concluídos": ("appointments", "Concluído"), "Exames laudados": ("exams", "Laudado"), "Produção conferida": ("billing", "Conferido")}
        for goal in all_rows:
            if goal["module"] != "goals" or (unit and str(goal.get("unit_id")) != unit):
                continue
            if goal["date"] > end.isoformat() or goal["end_date"] < start.isoformat():
                continue
            module, status = mapping[goal["indicator"]]
            eligible = [r for r in all_rows if r["module"] == module and r["status"] == status and goal["date"] <= r["date"] <= goal["end_date"] and (not goal.get("unit_id") or r.get("unit_id") == goal["unit_id"])]
            actual = sum(r["quantity"] for r in eligible) if module == "billing" else len(eligible)
            goal_results.append(dict(id=goal["id"], indicator=goal["indicator"], start=goal["date"], end=goal["end_date"], target=goal["target"], actual=actual, unit_id=goal.get("unit_id"), percent=round(100 * actual / goal["target"], 1) if goal["target"] else None))
        data = dict(start=start.isoformat(), end=end.isoformat(), unit=unit, summary=summary, dimensions=dimensions, epidemiology=epidemiology, goals=goal_results,
                    methodology="Faltas / (concluídos + faltas). Espera da fila atualmente aberta até a data final. Casos por 100 mil: pacientes confirmados distintos no período / população informada; não calculado sem base ou com filtro de unidade. Metas usam seu próprio período. Dados locais não substituem indicadores oficiais.")
        audit("export" if request.args.get("format") == "csv" else "read", "analytics"); db().commit()
        if request.args.get("format") == "csv":
            output = io.StringIO(); writer = csv.writer(output, delimiter=";")
            def line(*values):
                writer.writerow(["'" + str(v) if str(v).startswith(("=", "+", "-", "@", "\t", "\r")) else ("" if v is None else v) for v in values])
            line("Início", data["start"], "Fim", data["end"], "Unidade", unit or "Rede")
            for key, value in summary.items(): line(key, value)
            for dim, groups_ in dimensions.items():
                for row in groups_: line(dim, row["label"], row["count"])
            line("Território", "Agravo", "Notificações", "Confirmados distintos", "População", "Fonte", "Casos / 100 mil")
            for r in epidemiology: line(r["territory"], r["condition"], r["notifications"], r["confirmed_patients"], r["population"], r["source"], r["rate_per_100k"])
            line("Meta", "Início", "Fim", "Previsto", "Realizado", "%")
            for r in goal_results: line(r["indicator"], r["start"], r["end"], r["target"], r["actual"], r["percent"])
            return Response("\ufeff" + output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": 'attachment; filename="indicadores.csv"'})
        return jsonify(data)
