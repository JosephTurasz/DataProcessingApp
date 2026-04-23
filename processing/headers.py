import re
from utils.table_utils import pad_rows, trailing_empty_run, is_duplicate_header

class HeaderDetector:
    def __init__(self, logger):
        self.logger = logger
        self.last_header_result = None
        self.dropped_header_announced = False

    def detect_header(self, r1, r2, r3):
        if is_duplicate_header(r1, r2):
            return "duplicate"
        if self._detect_partial_header(r1, r3):
            return "partial"
        if self._detect_real_header(r1, r2, r3):
            return "real"
        return "none"

    def apply_header_result(self, result, lines):
        row1 = lines[0]

        if result == "real":
            return True, self._clean(row1), lines[1:]

        if result == "duplicate":
            return True, self._clean(row1), lines[2:]

        if result == "partial":
            padded, max_cols = pad_rows(lines[1:])
            headers = self._pad_headers(row1, max_cols)
            return True, headers, padded

        padded, max_cols = pad_rows(lines)
        return False, [f"Column{i+1}" for i in range(max_cols)], padded
    
    def drop_useless_header(self, df, has_header):
        if not has_header:
            return df, False
        placeholder = re.compile(r"^Column\d+$")
        if all(placeholder.match(str(c)) for c in df.columns):
            if not self.dropped_header_announced:
                self.dropped_header_announced = True
            df = df.iloc[1:].reset_index(drop=True)
            return df, False
        return df, True
    
    def analyze_and_log_header(self, df, has_header):
        raw = self.last_header_result
        col_names = [str(c).strip() for c in df.columns]

        if raw == "duplicate" and has_header and len(df) > 0:
            self.logger.log("[HEADER] Duplicate header detected.", "yellow")

            def row_matches_header(row_vals):
                return [c.lower() for c in col_names] == [
                    str(v).strip().lower() for v in row_vals]

            while len(df) > 0 and row_matches_header(df.iloc[0].tolist()):
                df = df.iloc[1:].reset_index(drop=True)
                self.logger.log("[HEADER] Dropped additional duplicate header row.", "yellow")

        if raw == "real":
            self.logger.log("[HEADER] Real header confirmed.", "green")
        elif raw == "partial":
            self.logger.log("[HEADER] Partial header applied.", "yellow")
        elif raw == "duplicate":
            pass
        elif not has_header:
            self.logger.log("[HEADER] No header detected.", "yellow")

        if has_header:
            return self.drop_useless_header(df, has_header)

        return df, has_header
    # ---------------- heuristics ----------------
    def _detect_partial_header(self, r1, r3):
        score = 0

        if sum(bool(c.strip()) for c in r1) <= max(1, int(sum(bool(c.strip()) for c in r3) * 0.6)):
            score += 1

        if trailing_empty_run(r1) > trailing_empty_run(r3):
            score += 1

        prefix = 0
        for c in r1:
            if c.strip():
                prefix += 1
            else:
                break

        if prefix and (sum(bool(c.strip()) for c in r1) - prefix) <= max(1, int(prefix * 0.2)):
            score += 1

        return score >= 2

    def _detect_real_header(self, r1, r2, r3):
        return (
            self._contains_keywords(r1)
            or self._similarity_rule(r1, r2, r3)
            or self._digit_density_rule(r1, r2, r3)
            or self._word_length_rule(r1, r2, r3)
        )

    def _contains_keywords(self, row):
        keywords = {
            "name", "address", "postcode", "post code", "zip", "email",
            "city", "town", "county", "country",
            "a1", "a2", "a3", "a4", "a5", "a6",
            "seed", "pid", "contact_id", "marketing_campaign", "brand_cd", "dps",
            "mailing address", "formatted name", "organisation",
            "mailing town", "mailing county", "mailing postcode",
        }

        cells = [str(c).strip().lower() for c in row if str(c).strip()]
        for cell in cells:
            if cell in keywords:
                return True
            if any(keyword in cell for keyword in keywords):
                return True

        return False

    def _similarity_rule(self, r1, r2, r3):
        # A header row should look less like the data rows than the data rows look like each other.
        # If r1 matches r3's type signature less than 75% as much as r2 does, r1 is likely the header.
        HEADER_SIMILARITY_THRESHOLD = 0.75

        def sig(row):
            return [(any(c.isalpha() for c in v), any(c.isdigit() for c in v)) for v in row]

        def score(a, b):
            return sum(x == y for x, y in zip(a, b))

        return score(sig(r1), sig(r2)) < score(sig(r2), sig(r3)) * HEADER_SIMILARITY_THRESHOLD

    def _digit_density_rule(self, r1, r2, r3):
        d1 = sum(any(c.isdigit() for c in v) for v in r1)
        d2 = sum(any(c.isdigit() for c in v) for v in r2)
        d3 = sum(any(c.isdigit() for c in v) for v in r3)
        return d1 < min(d2, d3) / 2

    def _word_length_rule(self, r1, r2, r3):
        def avg(row):
            vals = [len(v) for v in row if v.strip()]
            return sum(vals) / len(vals) if vals else 0
        return avg(r1) > max(avg(r2), avg(r3)) * 1.3

    def _clean(self, row):
        return [c.strip() for c in row]

    def _pad_headers(self, headers, max_cols):
        headers = self._clean(headers)
        if len(headers) < max_cols:
            headers += [f"Column{len(headers)+i+1}" for i in range(max_cols - len(headers))]
        return headers