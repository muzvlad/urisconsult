"""
TypedDict для данных FSM (Finite State Machine).

Описывает структуру данных, хранимых в FSM state.
"""
from typing import TypedDict, NotRequired


class WorkerFormData(TypedDict, total=False):
    """Данные работника в FSM state."""
    # ID (генерируется при сохранении)
    id: NotRequired[str]

    # Личные данные
    name: str
    citizenship: str
    gender: str
    position: str
    object: str
    object_address: str
    manager: str
    phone_main: str
    phone_additional: str
    email: str
    date: str

    # Доп. поля для России
    russia_marital_status: str
    russia_relatives_list: list[dict[str, str]]

    # Временные файлы документов (ключ = doc_key + '_temp_path')
    temp_files: list[str]

    # Режим исправления отклонённой анкеты
    editing_rejected: bool
    rejection_reasons: list[str]

    # Текущее исправляемое поле
    fix_current_field: str
    fix_reasons: list[str]
    fix_index: int

    # Режим редактирования
    editing_field: str
