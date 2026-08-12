from pydantic import BaseModel

class EngineSettingsModel(BaseModel):
    sync_batch_size: int
    work_hours_interval_minutes: int
    morning_window_interval_minutes: int
