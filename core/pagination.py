from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """§6: 'page, page_size (default 25, max 100)' on every list endpoint."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
