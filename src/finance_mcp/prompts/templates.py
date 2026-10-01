from mcp.types import GetPromptResult, Prompt, PromptArgument, PromptMessage, TextContent

PROMPTS = [
    Prompt(
        name="analyze_spending",
        description="Analyze spending patterns for a given time period",
        arguments=[
            PromptArgument(name="period",   description="Period e.g. 'last month', 'Q3 2026'", required=True),
            PromptArgument(name="focus",    description="Category to focus on (optional)",      required=False),
        ],
    ),
    Prompt(
        name="budget_review",
        description="Monthly budget review with actionable recommendations",
        arguments=[
            PromptArgument(name="budget_pln", description="Monthly budget in PLN", required=False),
        ],
    ),
    Prompt(
        name="currency_exposure",
        description="Analyze currency exposure across accounts",
        arguments=[],
    ),
]


async def resolve_prompt(name: str, arguments: dict) -> GetPromptResult:
    match name:
        case "analyze_spending":
            period = arguments.get("period", "last month")
            focus  = arguments.get("focus", "")
            focus_text = f" Szczególnie przeanalizuj kategorię **{focus}**." if focus else ""
            return GetPromptResult(
                description=f"Analiza wydatków — {period}",
                messages=[PromptMessage(role="user", content=TextContent(type="text", text=f"""
Proszę przeanalizuj moje wydatki za okres: **{period}**.{focus_text}

Użyj narzędzi:
1. `get_spending_summary` z odpowiednim period, group_by="category"
2. `search_transactions` żeby znaleźć największe pojedyncze wydatki

Raport powinien zawierać:
- Podział wydatków wg kategorii (tabela)
- Top 5 największych transakcji
- Konkretne 3 rekomendacje jak obniżyć koszty
- Ocenę trendu (czy wydaję więcej czy mniej niż zazwyczaj)
""".strip()))],
            )

        case "budget_review":
            budget = arguments.get("budget_pln", "10000")
            return GetPromptResult(
                description="Przegląd budżetu miesięcznego",
                messages=[PromptMessage(role="user", content=TextContent(type="text", text=f"""
Zrób pełny przegląd budżetu na bieżący miesiąc. Mój budżet: **{budget} PLN/miesiąc**.

Kroki:
1. Użyj `get_spending_summary` z period="this_month", group_by="category"
2. Użyj `search_transactions` z date_from=pierwszy dzień miesiąca

Pokaż mi:
- Budżet vs rzeczywiste wydatki per kategoria
- Prognoza na koniec miesiąca (jeśli tempo się utrzyma)
- Które kategorie przekraczają normę, a które mają zapas
- Czy uda mi się zaoszczędzić w tym miesiącu
""".strip()))],
            )

        case "currency_exposure":
            return GetPromptResult(
                description="Analiza ekspozycji walutowej",
                messages=[PromptMessage(role="user", content=TextContent(type="text", text="""
Przeanalizuj moją ekspozycję walutową na wszystkich kontach.

Kroki:
1. `search_transactions` z account="usd-account" — ile USD mam w przychodach/wydatkach
2. `get_exchange_rate` żeby przeliczyć USD na PLN
3. Porównaj z kontami w PLN

Powiedz mi:
- Jaki % moich przychodów jest w walutach obcych
- Jak zmiana kursu USD/PLN o ±10% wpłynęłaby na moją sytuację
- Czy warto hedgować ryzyko walutowe
""".strip()))],
            )

        case _:
            raise ValueError(f"Unknown prompt: {name}")
