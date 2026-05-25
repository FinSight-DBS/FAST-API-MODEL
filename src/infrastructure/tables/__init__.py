from src.infrastructure.tables.customer_table import CustomerTable
from src.infrastructure.tables.transaction_table import TransactionTable
from src.infrastructure.tables.weekly_report_table import WeeklyReportTable
from src.infrastructure.tables.monthly_report_table import MonthlyReportTable
from src.infrastructure.tables.detected_anomaly_table import DetectedAnomalyTable

__all__ = [
    "CustomerTable",
    "TransactionTable",
    "WeeklyReportTable",
    "MonthlyReportTable",
    "DetectedAnomalyTable",
]
