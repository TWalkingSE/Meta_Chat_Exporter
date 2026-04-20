"""
Meta Platforms Chat Exporter - Configuração
Gerenciamento de configuração persistente via arquivo JSON.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Caminho padrão do arquivo de configuração
DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.json"

# Valores padrão
DEFAULT_CONFIG = {
    "timezone_offset_hours": -3,
    "cache_enabled": True,
    "whisper_model": "base",
    "whisper_language": "pt",
    "export_format": "html_unified",
    "pagination_size": 500,
    "dark_mode": True,
    "log_level": "WARNING",
}


class Config:
    """Gerenciador de configuração persistente"""

    def __init__(self, config_path: Optional[Path] = None):
        self._path = config_path or DEFAULT_CONFIG_PATH
        self._data: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        """Carrega configuração do arquivo. Usa padrões se não existir."""
        if not self._path.exists():
            logger.debug("Arquivo de configuração não encontrado, usando padrões")
            return

        try:
            with open(self._path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)

            # Mesclar com padrões (preservar chaves novas nos padrões)
            for key, value in user_config.items():
                if key in DEFAULT_CONFIG:
                    # Validar tipo
                    expected_type = type(DEFAULT_CONFIG[key])
                    if isinstance(value, expected_type):
                        self._data[key] = value
                    else:
                        logger.warning(
                            "Config '%s': tipo inválido %s (esperado %s), usando padrão",
                            key, type(value).__name__, expected_type.__name__
                        )
                else:
                    # Aceitar chaves extras do usuário
                    self._data[key] = value

            logger.info("Configuração carregada de %s", self._path)
        except json.JSONDecodeError as e:
            logger.warning("Erro ao parsear config.json: %s. Usando padrões.", e)
        except Exception as e:
            logger.warning("Erro ao ler config.json: %s. Usando padrões.", e)

    def save(self) -> None:
        """Salva configuração atual no arquivo"""
        try:
            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            logger.debug("Configuração salva em %s", self._path)
        except Exception as e:
            logger.warning("Erro ao salvar configuração: %s", e)

    def get(self, key: str, default: Any = None) -> Any:
        """Retorna valor de configuração"""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Define valor de configuração e salva"""
        self._data[key] = value
        self.save()

    def get_all(self) -> Dict[str, Any]:
        """Retorna todas as configurações"""
        return dict(self._data)

    @property
    def timezone_offset_hours(self) -> int:
        return self._data["timezone_offset_hours"]

    @timezone_offset_hours.setter
    def timezone_offset_hours(self, value: int):
        self._data["timezone_offset_hours"] = value
        self.save()

    @property
    def cache_enabled(self) -> bool:
        return self._data["cache_enabled"]

    @property
    def whisper_model(self) -> str:
        return self._data["whisper_model"]

    @property
    def whisper_language(self) -> str:
        return self._data["whisper_language"]

    @property
    def pagination_size(self) -> int:
        return self._data["pagination_size"]

    @property
    def dark_mode(self) -> bool:
        return self._data["dark_mode"]

    @property
    def log_level(self) -> str:
        return self._data["log_level"]


# Instância global de configuração
config = Config()
