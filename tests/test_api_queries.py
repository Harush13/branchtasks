"""
Phase 3: §6's "always select_related on list endpoints... without it the
task list issues N+1 queries" — a query-count assertion is the actual
regression test for that rule; asserting the queryset merely calls
select_related wouldn't catch a serializer that reaches through an
un-prefetched relation.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from tasks.models import Task

pytestmark = pytest.mark.django_db


def make_task(branch, category, opener, **kwargs):
    kwargs.setdefault("title", "Fix the thing")
    return Task.objects.create(branch=branch, category=category, opened_by=opener, **kwargs)


def test_list_query_count_is_constant_across_row_count(
    member_client, member, manager, branch, category
):
    make_task(branch, category, member, assignee=manager)

    with CaptureQueriesContext(connection) as one_row:
        resp = member_client.get("/api/tasks")
    assert resp.status_code == 200

    for _ in range(19):
        make_task(branch, category, member, assignee=manager)

    with CaptureQueriesContext(connection) as many_rows:
        resp = member_client.get("/api/tasks")
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 20

    assert len(many_rows.captured_queries) == len(one_row.captured_queries)
