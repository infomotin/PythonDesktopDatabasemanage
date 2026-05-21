from django.core.paginator import Paginator, Page, EmptyPage, PageNotAnInteger


class PaginationHelper:
    @staticmethod
    def get_paginated_data(queryset, page: int = 1, per_page: int = 20, step: int = 7):
        paginator = Paginator(queryset, per_page)
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)
        page_range = PaginationHelper.get_page_range(page_obj.paginator.num_pages, page_obj.number, step)
        return page_obj, page_range

    @staticmethod
    def paginate_list(data: list, page: int = 1, per_page: int = 20):
        p = Paginator(data, per_page)
        try:
            return p.page(page)
        except (PageNotAnInteger, EmptyPage):
            return p.page(1)

    @staticmethod
    def get_page_range(total_pages: int, current: int, step: int = 7) -> Tuple[int, int]:
        if total_pages <= 1:
            return 1
        half = step // 2
        start = max(1, current - half)
        end = min(total_pages, start + step - 1)
        if end - start < step - 1:
            start = max(1, end - step + 1)
        return start, end

    @staticmethod
    def build_page_context(page_obj: Page, page_range: Tuple = None, extra: Dict = None) -> Dict:
        ctx = {
            "page_obj": page_obj,
            "object_list": page_obj.object_list,
            "page_range": page_range or PaginationHelper.get_page_range(
                page_obj.paginator.num_pages, page_obj.number,
            ),
        }
        return {**ctx, **(extra or {})}
