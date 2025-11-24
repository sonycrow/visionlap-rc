import json
from pathlib import Path
import config as global_config
import os


BASE = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE / 'camera_config.json'

# Llaves de configuración que consideramos relevantes para la cámara
CAMERA_KEYS = [
    'CAMERA_IDX',
    'CAMERA_RESOLUTION',
    'CAMERA_FPS',
    'CAMERA_AUTOFOCUS',
    'CAMERA_FOCUS',
    'CAMERA_AUTO_EXPOSURE',
    'CAMERA_EXPOSURE',
    'CAMERA_GAIN',
    'CAMERA_BRIGHTNESS',
    'CAMERA_CONTRAST',
    'FINISH_LINE'
]


def _read_file():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
        except Exception:
            return None
    return None


def _write_file(data: dict):
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def _module_value(key):
    # Intentar leer desde el módulo config (global_config)
    return getattr(global_config, key, None)


def load_or_create_from_module_config(app_config=None):
    """
    Cargar la configuración persistente desde `camera_config.json` si existe.
    Si no existe, crearla a partir de los valores ya presentes en el módulo
    `config` (o `app_config` si se pasa) y persistirla.
    También aplica los valores leídos al módulo `config` en memoria.
    """
    data = _read_file()
    if data is None:
        # Construir desde module config o app_config
        out = {}
        for k in CAMERA_KEYS:
            v = None
            if app_config and k in app_config:
                v = app_config[k]
            else:
                v = _module_value(k)

            # Serializar tuplas a listas para JSON
            if isinstance(v, tuple):
                v = list(v)

            out[k] = v

        # Normalizar resolution: si está en CAMERA_RESOLUTION como lista -> tupla
        if out.get('CAMERA_RESOLUTION') and isinstance(out['CAMERA_RESOLUTION'], list):
            out['CAMERA_RESOLUTION'] = out['CAMERA_RESOLUTION']

        _write_file(out)
        data = out

    # Aplicar los valores leídos al módulo config en memoria
    _apply_to_module(data)
    return data


def _apply_to_module(d: dict):
    # Convertir listas a tuplas donde corresponda (CAMERA_RESOLUTION, FINISH_LINE)
    for k, v in d.items():
        if k == 'CAMERA_RESOLUTION' and isinstance(v, list):
            setattr(global_config, k, (int(v[0]), int(v[1])))
            continue
        if k == 'FINISH_LINE' and isinstance(v, list):
            # Esperamos [[x1,y1],[x2,y2]]
            try:
                fl = tuple((tuple(p) for p in v))
                setattr(global_config, k, fl)
                continue
            except Exception:
                pass

        # Intentar castear a int cuando sea apropiado
        if isinstance(v, str) and v.isdigit():
            try:
                setattr(global_config, k, int(v))
                continue
            except Exception:
                pass

        setattr(global_config, k, v)


def get_current():
    """Devolver la configuración actualmente en disco (y aplicada en memoria)."""
    data = _read_file()
    if data is None:
        data = load_or_create_from_module_config()
    return data


def save_and_apply(new_cfg: dict, vision_system=None):
    """
    Actualiza la configuración persistente y aplica los valores al módulo `config`.
    Si se pasa `vision_system`, intenta aplicar la reconfiguración en tiempo de ejecución
    reiniciando el detector (stop/start) cuando sea necesario.
    """
    cur = get_current() or {}
    merged = dict(cur)
    for k, v in new_cfg.items():
        if k not in CAMERA_KEYS:
            # Ignorar claves desconocidas
            continue
        merged[k] = v

    # Normalizar: si CAMERA_RESOLUTION viene como dict o lista, convertir a lista para JSON
    if 'CAMERA_RESOLUTION' in merged and isinstance(merged['CAMERA_RESOLUTION'], (tuple,)):
        merged['CAMERA_RESOLUTION'] = list(merged['CAMERA_RESOLUTION'])

    _write_file(merged)

    # Aplicar a módulo
    _apply_to_module(merged)

    # Si se proporcionó vision_system, intentar reconfigurar en caliente
    if vision_system is not None:
        try:
            # Actualizar atributos que RaceSystem usa
            if 'CAMERA_IDX' in merged:
                vision_system.camera_idx = int(merged['CAMERA_IDX'])
            if 'CAMERA_RESOLUTION' in merged:
                res = merged['CAMERA_RESOLUTION']
                if isinstance(res, list):
                    vision_system.resolution = (int(res[0]), int(res[1]))
            # Si está en marcha, reiniciarlo para aplicar cambios
            if getattr(vision_system, 'running', False):
                try:
                    vision_system.stop()
                except Exception:
                    pass
                try:
                    vision_system.start()
                except Exception:
                    pass
        except Exception:
            pass

    return merged
