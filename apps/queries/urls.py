from django.urls import path
from apps.db_query_history import views

app_name = "queries"
urlpatterns = [
    path("", views.QueryListView.as_view(), name="list"),
    path("<int:query_id>/", views.QueryDetailView.as_view(), name="detail"),
    path("<int:query_id>/results/", views.QueryResultsView.as_view(), name="results"),
    path("import-sql/", views.ImportSQLFromExcelView.as_view(), name="import_sql"),
    path("model/", views.QueryModelView.as_view(), name="model"),
    path("model/templates", views.QueryTemplateView.as_view(), name="templates"),
]
