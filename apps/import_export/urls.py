from django.urls import path
from apps.import_export import views

app_name = "import_export"
urlpatterns = [
    path("", views.ImportExportDashboard.as_view(), name="dashboard"),
    path("import-excel/", views.ImportExcelView.as_view(), name="import_excel"),
    path("export-excel/", views.ExportExcelView.as_view(), name="export_excel"),
    path("excel-to-sql/", views.ExcelToSQLView.as_view(), name="excel_to_sql"),
    path("import-preview/", views.ImportPreviewView.as_view(), name="import_preview"),
    path("api/import/", views.ImportExcelAPI.as_view(), name="api_import"),
    path("api/export/", views.ExportExcelAPI.as_view(), name="api_export"),
    path("tasks/", views.ImportExportTaskListView.as_view(), name="task_list"),
    path("tasks/<uuid:task_id>/", views.ImportExportTaskDetail.as_view(), name="task_detail"),
]
