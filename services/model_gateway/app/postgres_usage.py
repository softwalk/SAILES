"""Durable pre-call model budget reservations and model-call audit records."""
import json
from uuid import UUID, uuid4


class ModelBudgetError(RuntimeError):
    pass


class PostgresModelUsageRepository:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    @classmethod
    def from_dsn(cls, dsn: str):
        def factory():
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError("PSYCOPG_NOT_INSTALLED_FROM_APPROVED_LOCK") from exc
            return psycopg.connect(dsn)
        return cls(factory)

    @staticmethod
    def _tenant(cursor, tenant_id: str):
        cursor.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))

    def reserve(self, tenant_id: str, task_alias: str, units: int, daily_limit: int,
                run_id: str | None = None) -> str:
        if units < 1 or daily_limit < 1 or units > daily_limit:
            raise ModelBudgetError("DAILY_BUDGET_EXCEEDED_PRECALL")
        reservation_id = str(uuid4())
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                self._tenant(cursor, tenant_id)
                if run_id:
                    cursor.execute(
                        "SELECT EXISTS(SELECT 1 FROM graph_run WHERE tenant_id=%s AND id=%s)",
                        (tenant_id, run_id),
                    )
                    if cursor.fetchone()[0] is not True:
                        raise ModelBudgetError("MODEL_RUN_NOT_FOUND_PRECALL")
                cursor.execute(
                    """SELECT id,reserved_units FROM model_budget_reservation
                       WHERE tenant_id=%s AND budget_date=current_date AND status='RESERVED'
                         AND expires_at <= now() FOR UPDATE""",
                    (tenant_id,),
                )
                expired_rows = cursor.fetchall()
                expired = sum(int(row[1]) for row in expired_rows)
                cursor.execute(
                    """INSERT INTO model_budget_daily (tenant_id,budget_date)
                       VALUES (%s,current_date) ON CONFLICT DO NOTHING""",
                    (tenant_id,),
                )
                cursor.execute(
                    """UPDATE model_budget_daily SET reserved_units=GREATEST(0,reserved_units-%s),updated_at=now()
                       WHERE tenant_id=%s AND budget_date=current_date""",
                    (expired, tenant_id),
                )
                cursor.execute(
                    """UPDATE model_budget_reservation SET status='RELEASED',settled_at=now()
                       WHERE tenant_id=%s AND budget_date=current_date AND status='RESERVED' AND expires_at <= now()""",
                    (tenant_id,),
                )
                cursor.execute(
                    """SELECT reserved_units,spent_units FROM model_budget_daily
                       WHERE tenant_id=%s AND budget_date=current_date FOR UPDATE""",
                    (tenant_id,),
                )
                reserved, spent = map(int, cursor.fetchone())
                if reserved + spent + units > daily_limit:
                    raise ModelBudgetError("DAILY_BUDGET_EXCEEDED_PRECALL")
                cursor.execute(
                    """UPDATE model_budget_daily SET reserved_units=reserved_units+%s,updated_at=now()
                       WHERE tenant_id=%s AND budget_date=current_date""",
                    (units, tenant_id),
                )
                cursor.execute(
                    """INSERT INTO model_budget_reservation
                       (id,tenant_id,budget_date,task_alias,reserved_units,status,expires_at)
                       VALUES (%s,%s,current_date,%s,%s,'RESERVED',now()+interval '2 minutes')""",
                    (reservation_id, tenant_id, task_alias, units),
                )
        return reservation_id

    def settle(self, reservation_id: str, request, *, actual_units: int, provider: str,
               model_id: str, latency_ms: int, outcome: str, redaction_applied: bool) -> str:
        call_id = reservation_id
        correlation_id = request.correlation_id or request.run_id or call_id
        try:
            correlation_id = str(UUID(str(correlation_id)))
        except (ValueError, TypeError, AttributeError):
            correlation_id = call_id
        run_id = request.run_id
        if run_id:
            try:
                run_id = str(UUID(str(run_id)))
            except (ValueError, TypeError, AttributeError):
                raise ModelBudgetError("MODEL_RUN_ID_INVALID")
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                self._tenant(cursor, request.tenant_id)
                cursor.execute(
                    """SELECT reserved_units,status,budget_date FROM model_budget_reservation
                       WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                    (request.tenant_id, reservation_id),
                )
                row = cursor.fetchone()
                if row is None or row[1] != "RESERVED":
                    raise ModelBudgetError("MODEL_BUDGET_RESERVATION_INVALID")
                reserved, _, budget_date = row
                charged = max(0, int(actual_units))
                cursor.execute(
                    """UPDATE model_budget_daily
                       SET reserved_units=GREATEST(0,reserved_units-%s),spent_units=spent_units+%s,updated_at=now()
                       WHERE tenant_id=%s AND budget_date=%s""",
                    (reserved, charged, request.tenant_id, budget_date),
                )
                cursor.execute(
                    """UPDATE model_budget_reservation SET actual_units=%s,status=%s,settled_at=now()
                       WHERE tenant_id=%s AND id=%s""",
                    (charged, "SETTLED" if outcome == "SUCCESS" else "RELEASED", request.tenant_id, reservation_id),
                )
                cursor.execute(
                    """INSERT INTO model_call
                       (id,tenant_id,run_id,task_alias,provider,model_id,prompt_version,data_classification,
                        input_tokens,output_tokens,cost_units,latency_ms,estimated_cost,outcome,
                        redaction_applied,correlation_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NULL,NULL,%s,%s,NULL,%s,%s,%s)""",
                    (call_id, request.tenant_id, run_id, request.task_alias, provider, model_id,
                     request.prompt_version, request.data_classification, charged, latency_ms, outcome,
                     redaction_applied, correlation_id),
                )
                audit_action = "MODEL_CALL_COMPLETED" if outcome == "SUCCESS" else "MODEL_CALL_FAILED"
                cursor.execute(
                    """SELECT app.append_audit_event(%s,'SERVICE','model-gateway',%s,
                              'MODEL_CALL',%s,NULL,%s::jsonb,%s)""",
                    (request.tenant_id, audit_action, call_id,
                     json.dumps([outcome, provider, model_id]), correlation_id),
                )
        return call_id
