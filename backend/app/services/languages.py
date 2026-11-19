"""Languages students can use. Judge0 ids come from the Judge0 CE v1.13.1 docs."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    key: str  # what our API and database use
    label: str  # what students see
    judge0_id: int
    # Slower languages get more time, so a correct Python or Java answer
    # is not marked "too slow" only because of the language.
    time_multiplier: float = 1.0
    # Java needs more memory just to start the JVM.
    min_memory_kb: int = 0
    filename: str = "main"


LANGUAGES: dict[str, Language] = {
    "c": Language("c", "C (GCC 9.2)", 50, filename="main.c"),
    "cpp": Language("cpp", "C++ (GCC 9.2)", 54, filename="main.cpp"),
    "java": Language("java", "Java (OpenJDK 13)", 62, time_multiplier=2.0, min_memory_kb=262144, filename="Main.java"),
    "python": Language("python", "Python (3.8)", 71, time_multiplier=3.0, filename="main.py"),
}


def get_language(key: str) -> Language | None:
    return LANGUAGES.get(key)
