from schemas import SearchParams

# ============================================================================
# Action Search Configuration
# ============================================================================

# Параметры поиска для внутренней базы (1gl.ru)
ACTION_SEARCH_BASE_PARAMS = SearchParams(
    pubAlias="bss.plus",
    fixedregioncode="77",
    isUseHints="false",
    sortby="Relevance",
    status="actual",
    dataformat="json",
    pubdivid=1,
    pubId=220,
    fstring="",  # Устанавливается динамически при вызове
)

# Формат URL для документов из внутренней базы
ACTION_URL_FORMAT = "https://1gl.ru/?#/document/{moduleId}/{id}"

# Дефолтный score для внутренних документов (высокий приоритет)
ACTION_DEFAULT_SCORE = 0.8

# Количество страниц результатов для загрузки
ACTION_PAGES = 1


# ============================================================================
# Yandex Search Configuration
# ============================================================================

# Веса доменов для ранжирования результатов Yandex
# Доверенные юридические и налоговые источники получают высокий вес
YANDEX_DOMAIN_WEIGHTS: dict[str, float] = {
    "www.consultant.ru": 1.0,  # КонсультантПлюс - максимальный приоритет
    "base.garant.ru": 0.95,  # Гарант
    "minfin.gov.ru": 0.9,  # Министерство финансов
    "nalog.gov.ru": 0.9,  # ФНС
    "ppt.ru": 0.7,  # Право.ru
    "journal.tinkoff.ru": 0.5,  # Тинькофф журнал
}

# Вес для неизвестных доменов (низкий приоритет)
YANDEX_DEFAULT_WEIGHT = 0.1
