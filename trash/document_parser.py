# document_parser.py

import json
import logging
import re

# Настраиваем логирование. __name__ автоматически подставит "document_parser"
# Это позволяет централизованно управлять выводом логов из главного скрипта.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DocumentParser:
    """
    Класс для парсинга сложной JSON-структуры документа, получаемого от API,
    и извлечения из него чистого, связного текста.
    """
    def __init__(self):
        """Инициализирует парсер, создавая пустой список для текстовых фрагментов."""
        self.texts = []

    def parse(self, document: dict) -> str:
        """
        Главный метод. Принимает на вход JSON-документ в виде словаря
        и возвращает единую строку с очищенным текстом.
        """
        # Сбрасываем состояние перед каждым новым парсингом
        self.texts = []
        try:
            # Основная точка входа в рекурсивный парсинг
            if "data" in document and "document" in document["data"]:
                self._process_document(document["data"]["document"])
            
            # После обхода всего дерева JSON, объединяем и чистим текст
            return self._concatenate_and_clean_texts()

        except Exception as e:
            logger.error(f"Критическая ошибка при парсинге документа: {e}", exc_info=True)
            return ""

    def _process_document(self, document_data: dict):
        """Обрабатывает основной "документный" блок JSON."""
        if not isinstance(document_data, dict):
            return

        content = document_data.get("content")
        if content:
            # Часто основной контент является строкой, которую нужно дополнительно распарсить
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    logger.warning("Не удалось распарсить 'content' как JSON, обрабатываем как текст.")
                    self.texts.append(content)
                    return
            
            if isinstance(content, dict) and "body" in content:
                self._process_content_body(content["body"])

    def _process_content_body(self, body: dict):
        """Рекурсивно обходит 'body' и его дочерние элементы ('children')."""
        if not isinstance(body, dict):
            return
        
        # Рекурсивно проходим по всем дочерним элементам
        if "children" in body:
            for child in body["children"]:
                self._extract_texts_from_children(child)
    
    def _extract_texts_from_children(self, element: dict):
        """
        Рекурсивно извлекает текст из элемента. Это ядро парсера,
        которое "знает", в каких полях и типах элементов искать текст.
        """
        if not isinstance(element, dict):
            return

        # Если элемент имеет тип 'text', извлекаем его значение из 'options'
        if element.get("type") == "text":
            value = element.get("options", {}).get("value")
            if value and isinstance(value, str):
                self.texts.append(value)
        
        # Если у элемента есть свои дочерние элементы, продолжаем обход рекурсивно
        if "children" in element:
            for child in element["children"]:
                self._extract_texts_from_children(child)

    def _concatenate_and_clean_texts(self) -> str:
        """Объединяет все найденные текстовые фрагменты в одну строку и очищает ее."""
        combined_text = " ".join(self.texts)
        return self._clean_text(combined_text)

    @staticmethod
    def _clean_text(text: str) -> str:
        """
        Статический метод для очистки текста от лишних пробелов,
        спецсимволов и некорректной пунктуации с помощью регулярных выражений.
        """
        s = text
        s = s.replace("\n", " ").replace("\r", " ") # Заменяем переносы строк на пробелы
        s = s.replace("\xa0", " ") # Заменяем неразрывный пробел
        s = re.sub(r'\s+([,.!?;:)\]])', r'\1', s)  # Удаляем пробелы перед знаками препинания
        s = re.sub(r'([(\[])\s+', r'\1', s)  # Удаляем пробелы после открывающих скобок
        s = re.sub(r'\s{2,}', ' ', s)  # Сжимаем множественные пробелы в один
        return s.strip()

# --- БЛОК ДЛЯ ТЕСТОВОГО ЗАПУСКА ---
if __name__ == "__main__":

    def main_test():
        """
        Тестирует DocumentParser на примере локального JSON-файла.
        """
        print("--- Запускаем тестовый прогон DocumentParser ---")
        parser = DocumentParser()
        example_path = "example_document.json" # Имя файла для теста

        try:
            with open(example_path, "r", encoding="utf-8") as f:
                document_json = json.load(f)

            print(f"Файл '{example_path}' успешно загружен. Начинаем парсинг...")
            
            cleaned_text = parser.parse(document_json)
            
            print("\n--- Результат парсинга (очищенный текст) ---")
            # Выводим первые 1000 символов для предпросмотра
            print(cleaned_text[:1000] + "..." if len(cleaned_text) > 1000 else cleaned_text)
            
            print(f"\nОбщая длина извлеченного текста: {len(cleaned_text)} символов.")

        except FileNotFoundError:
            print(f"\nОШИБКА: Тестовый файл '{example_path}' не найден.")
            print("ПОДСКАЗКА: Запустите search_client.py, скопируйте JSON одного из документов")
            print(f"и сохраните его в файл с именем '{example_path}' для тестирования парсера.")
        except json.JSONDecodeError as e:
            print(f"\nОШИБКА: Неверный формат JSON в файле '{example_path}': {e}")
        except Exception as e:
            print(f"\nОШИБКА: Произошла непредвиденная ошибка: {e}")
        
        print("\n--- Тестовый прогон завершен ---")

    main_test()