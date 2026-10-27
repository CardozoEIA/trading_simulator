"""A tiny in-memory stand-in for the Supabase client, enough for the service tests."""
from types import SimpleNamespace


class FakeQuery:
    def __init__(self, db, table):
        self.db, self.table = db, table
        self.filters, self.orders, self._limit, self._range = [], [], None, None
        self.action, self.payload, self.conflict = "select", None, None

    # filters -------------------------------------------------------------------------------------
    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.filters.append((column, "eq", value))
        return self

    def in_(self, column, values):
        self.filters.append((column, "in", list(values)))
        return self

    def gte(self, column, value):
        self.filters.append((column, "gte", value))
        return self

    def lte(self, column, value):
        self.filters.append((column, "lte", value))
        return self

    def order(self, column, desc=False):
        self.orders.append((column, desc))
        return self

    def limit(self, count):
        self._limit = count
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    # writes --------------------------------------------------------------------------------------
    def insert(self, payload):
        self.action, self.payload = "insert", payload
        return self

    def upsert(self, payload, on_conflict=None):
        self.action, self.payload, self.conflict = "upsert", payload, on_conflict
        return self

    def update(self, payload):
        self.action, self.payload = "update", payload
        return self

    def delete(self):
        self.action = "delete"
        return self

    # run -----------------------------------------------------------------------------------------
    def _matches(self, row):
        for column, op, value in self.filters:
            have = row.get(column)
            if op == "eq" and have != value:
                return False
            if op == "in" and have not in value:
                return False
            if op == "gte" and not (have is not None and have >= value):
                return False
            if op == "lte" and not (have is not None and have <= value):
                return False
        return True

    def execute(self):
        if self.db.fail:
            raise RuntimeError("database down")
        rows = self.db.tables.setdefault(self.table, [])
        if self.action == "insert":
            items = self.payload if isinstance(self.payload, list) else [self.payload]
            stored = [dict(i, id=i.get("id", f"{self.table}-{len(rows) + n + 1}")) for n, i in enumerate(items)]
            rows.extend(stored)
            return SimpleNamespace(data=stored)
        if self.action == "upsert":
            keys = (self.conflict or "id").split(",")
            for item in self.payload:
                existing = next((r for r in rows if all(r.get(k) == item.get(k) for k in keys)), None)
                if existing:
                    existing.update(item)
                else:
                    rows.append(dict(item))
            return SimpleNamespace(data=self.payload)
        if self.action == "update":
            hit = [r for r in rows if self._matches(r)]
            for r in hit:
                r.update(self.payload)
            return SimpleNamespace(data=hit)
        if self.action == "delete":
            hit = [r for r in rows if self._matches(r)]
            self.db.tables[self.table] = [r for r in rows if r not in hit]
            return SimpleNamespace(data=hit)

        found = [r for r in rows if self._matches(r)]
        for column, desc in reversed(self.orders):
            found.sort(key=lambda r: str(r.get(column, "")), reverse=desc)
        if self._range:
            found = found[self._range[0] : self._range[1] + 1]
        if self._limit is not None:
            found = found[: self._limit]
        return SimpleNamespace(data=[dict(r) for r in found], count=len(found))


class FakeSupabase:
    def __init__(self, **tables):
        self.tables = {name: [dict(r) for r in rows] for name, rows in tables.items()}
        self.fail = False

    def table(self, name):
        return FakeQuery(self, name)
