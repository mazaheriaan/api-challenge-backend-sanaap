from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class DocumentPagination(PageNumberPagination):
    """Standard pagination for document listings."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        # Calculate total file size for current page
        total_file_size = sum(
            doc.get("file_size", 0)
            for doc in data
            if isinstance(doc, dict) and "file_size" in doc
        )

        return Response(
            OrderedDict(
                [
                    ("count", self.page.paginator.count),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("page_size", self.page_size),
                    ("total_pages", self.page.paginator.num_pages),
                    ("current_page", self.page.number),
                    ("total_file_size", total_file_size),
                    ("results", data),
                ],
            ),
        )


class LargeDocumentPagination(PageNumberPagination):
    """Pagination for admin views with more items per page."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    ("count", self.page.paginator.count),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("page_size", self.page_size),
                    ("total_pages", self.page.paginator.num_pages),
                    ("current_page", self.page.number),
                    ("results", data),
                ],
            ),
        )


class SmallDocumentPagination(PageNumberPagination):
    """Pagination for mobile or limited views."""

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50
