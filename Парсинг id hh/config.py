# # =========================================================
# # HH
# # =========================================================

# HH_BASE_URL = "https://hh.ru/search/vacancy"

# # Сколько вакансий просить на странице.
# # HH поддерживает 20 / 50 / 100.
# ITEMS_ON_PAGE = 100


# # =========================================================
# # PROFESSIONAL ROLES
# # =========================================================

# PROFESSIONAL_ROLES = [
#     156,
#     160,
#     10,
#     12,
#     150,
#     25,
#     165,
#     34,
#     36,
#     73,
#     155,
#     96,
#     164,
#     104,
#     157,
#     107,
#     112,
#     113,
#     148,
#     114,
#     116,
#     121,
#     124,
#     125,
#     126,
# ]


# # =========================================================
# # PARSER
# # =========================================================

# CONCURRENCY = 4

# MAX_RETRIES = 4
# REQUEST_TIMEOUT = 30

# REQUEST_DELAY = (1.0, 2.5)


# # =========================================================
# # STORAGE
# # =========================================================

# IDS_FILE = "data.vacancy_ids.txt"
# LOG_FILE = "logs/parser.log"

HH_BASE_URL = "https://hh.ru/search/vacancy"

ITEMS_ON_PAGE = 100

KEYWORDS = [
    # Программирование
    "Python",
    "Java",
    "JavaScript",
    "TypeScript",
    "C++",
    "C#",
    "Go",
    "Golang",
    "PHP",
    "Ruby",
    "Kotlin",
    "Swift",
    "Rust",
    "Scala",
    "Dart",

    # Web
    "Frontend",
    "Backend",
    "Fullstack",
    "Full Stack",
    "Web Developer",
    "Web-разработчик",

    # Data / ML / AI
    "Data Scientist",
    "Data Science",
    "Machine Learning",
    "Machine Learning Engineer",
    "ML Engineer",
    "ML",
    "AI",
    "Artificial Intelligence",
    "Deep Learning",
    "NLP",
    "Computer Vision",
    "Data Analyst",
    "Data Analytics",
    "Data Engineer",
    "Data Engineering",
    "BI Analyst",
    "BI",
    "Business Intelligence",

    # Аналитика
    "Аналитик данных",
    "Системный аналитик",
    "Бизнес-аналитик",
    "Продуктовый аналитик",
    "Product Analyst",
    "System Analyst",
    "Business Analyst",
    "Product Analytics",

    # QA
    "QA",
    "QA Engineer",
    "QA Automation",
    "QA Automation Engineer",
    "Тестировщик",
    "Тестировщик ПО",
    "Автотесты",
    "Automation Tester",
    "SDET",

    # DevOps / инфраструктура
    "DevOps",
    "DevOps Engineer",
    "SRE",
    "Site Reliability Engineer",
    "Cloud",
    "Cloud Engineer",
    "Kubernetes",
    "Docker",
    "Terraform",
    "Ansible",

    # Администрирование
    "Системный администратор",
    "System Administrator",
    "Linux",
    "Windows Server",
    "Администратор Linux",

    # Базы данных
    "SQL",
    "PostgreSQL",
    "MySQL",
    "Oracle",
    "MongoDB",
    "Redis",
    "Database",
    "DBA",

    # Архитектура
    "Software Architect",
    "Solution Architect",
    "Архитектор ПО",
    "Системный архитектор",

    # 1С
    "1С",
    "1С программист",
    "1С разработчик",

    # Мобильная разработка
    "Android",
    "iOS",
    "Mobile Developer",
    "Android Developer",
    "iOS Developer",

    # Другое IT
    "IT",
    "ИТ",
    "Software Developer",
    "Software Engineer",
    "Developer",
    "Разработчик",
    "Программист",
]

PROFESSIONAL_ROLES = [
    156, 160, 10, 12, 150, 25, 165, 34,
    36, 73, 155, 96, 164, 104, 157, 107,
    112, 113, 148, 114, 116, 121, 124, 125, 126
]

CONCURRENCY = 4
MAX_RETRIES = 4
REQUEST_TIMEOUT = 30

REQUEST_DELAY = (1.0, 2.5)

IDS_FILE = "data/vacancy_ids.txt"
LOG_FILE = "logs/parser.log"