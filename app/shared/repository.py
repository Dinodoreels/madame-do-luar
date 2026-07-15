from typing import Any, Optional

import db_client


class SupabaseRepository:
    table: str

    def __init__(self, table: Optional[str] = None):
        if table:
            self.table = table

    def list(self, *, select: str = "*", filters: str = "", limit: int = 100, order: Optional[str] = None, timeout: Optional[int] = None) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "select": select,
            "filtros": filters,
            "limit": limit,
        }
        if order:
            kwargs["order"] = order
        if timeout is not None:
            kwargs["timeout"] = timeout
        return db_client.listar_registros(self.table, **kwargs)

    def get_by_id(self, column: str, value: Any) -> Optional[dict[str, Any]]:
        return db_client.buscar_por_id(self.table, column, value)

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        return db_client.criar_registro(self.table, payload)

    def update(self, column: str, value: Any, payload: dict[str, Any]) -> dict[str, Any]:
        return db_client.atualizar_registro(self.table, column, value, payload)


def log_event(*args, **kwargs):
    return db_client.registrar_log(*args, **kwargs)


def audit_event(*args, **kwargs):
    return db_client.registrar_auditoria(*args, **kwargs)
