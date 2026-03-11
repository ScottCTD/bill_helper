from __future__ import annotations

from io import BytesIO

from backend.schemas_finance import DashboardFilterGroupSummary, DashboardMonthlyTrendPoint


def _load_pyplot():
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    return plt


def render_income_expense_trend(
    monthly_trend: list[DashboardMonthlyTrendPoint],
    *,
    currency_code: str,
) -> BytesIO:
    plt = _load_pyplot()
    months = [point.month for point in monthly_trend]
    income_values = [point.income_total_minor / 100 for point in monthly_trend]
    expense_values = [point.expense_total_minor / 100 for point in monthly_trend]

    figure, axis = plt.subplots(figsize=(8.5, 4.8), dpi=180)
    axis.plot(months, income_values, color="#1f7a1f", marker="o", linewidth=2.6, label="Income")
    axis.plot(months, expense_values, color="#b42318", marker="o", linewidth=2.6, label="Expense")
    axis.set_title(f"Income vs Expense ({currency_code})", fontsize=15, fontweight="bold")
    axis.set_ylabel(currency_code, fontsize=11)
    axis.tick_params(axis="x", rotation=25, labelsize=10)
    axis.tick_params(axis="y", labelsize=10)
    axis.grid(axis="y", alpha=0.25)
    axis.legend(frameon=False, fontsize=10)
    figure.tight_layout()
    return _figure_to_png(figure, plt)


def render_expense_by_filter_group(
    filter_groups: list[DashboardFilterGroupSummary],
    *,
    currency_code: str,
) -> BytesIO:
    plt = _load_pyplot()
    ordered = sorted(filter_groups, key=lambda item: item.total_minor, reverse=True)
    labels = [item.name for item in ordered]
    values = [item.total_minor / 100 for item in ordered]
    colors = [item.color or "#667085" for item in ordered]

    figure_height = max(4.0, 0.65 * max(1, len(labels)))
    figure, axis = plt.subplots(figsize=(8.5, figure_height), dpi=180)
    bars = axis.barh(labels, values, color=colors)
    axis.invert_yaxis()
    axis.set_title(f"Expense by Filter Group ({currency_code})", fontsize=15, fontweight="bold")
    axis.set_xlabel(currency_code, fontsize=11)
    axis.tick_params(axis="both", labelsize=10)
    axis.grid(axis="x", alpha=0.2)
    for bar, value in zip(bars, values, strict=False):
        axis.text(
            bar.get_width() + max(values or [0]) * 0.015,
            bar.get_y() + bar.get_height() / 2,
            f"{value:,.2f}",
            va="center",
            fontsize=9,
            color="#101828",
        )
    figure.tight_layout()
    return _figure_to_png(figure, plt)


def _figure_to_png(figure, plt) -> BytesIO:
    buffer = BytesIO()
    figure.savefig(buffer, format="png", bbox_inches="tight", facecolor="white")
    buffer.seek(0)
    plt.close(figure)
    return buffer
