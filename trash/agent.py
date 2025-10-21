# agent.py

import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain import hub

from tools import GlavbukhSearchTool

# --- Настройка ---
# Загружаем переменные окружения (OPENAI_API_KEY)
load_dotenv()

# Проверяем наличие ключа API
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("Необходимо установить переменную окружения OPENAI_API_KEY")

# --- Инициализация компонентов Агента ---

# 1. Инициализируем LLM от OpenAI
# Используем gpt-4-turbo для лучших результатов в следовании инструкциям
llm = ChatOpenAI(model="google/gemini-2.5-pro", temperature=0)

# 2. Создаем список инструментов, доступных Агенту
# В нашем случае это только один инструмент для поиска
tools = [GlavbukhSearchTool()]

# 3. Загружаем готовый промпт (шаблон) для ReAct агента
# Этот промпт объясняет LLM, как использовать инструменты
prompt = hub.pull("hwchase17/react")

# --- Создание и запуск Агента ---

# 4. Создаем самого Агента, передавая ему LLM, инструменты и промпт
agent = create_react_agent(llm, tools, prompt)

# 5. Создаем "исполнителя" (Executor), который будет управлять циклами ReAct
# (Reasoning -> Action -> Observation)
# verbose=True позволяет видеть "мысли" агента в консоли
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)


# --- Основная функция ---
def main():
    """
    Основная функция для взаимодействия с Агентом.
    """
    print("🤖 Агент-помощник по бухгалтерии готов к работе.")
    print("Введите ваш вопрос или 'выход' для завершения.")
    
    while True:
        user_query = input("\nВаш вопрос: ")
        if user_query.lower() == 'выход':
            break
        
        # Запускаем агента с запросом пользователя
        response = agent_executor.invoke({
            "input": user_query,
        })
        
        # Выводим финальный ответ агента
        print("\n💡 Ответ Агента:")
        print(response["output"])


if __name__ == "__main__":
    main()