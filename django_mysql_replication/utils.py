from django.apps import apps
from django.db.models import Model

model_cache = {}


def get_app_model(table_name) -> Model:
    if table_name in model_cache:
        return model_cache[table_name]

    for model in apps.get_models():
        if model._meta.db_table == table_name:
            model_cache[table_name] = model
            return model
    raise KeyError
