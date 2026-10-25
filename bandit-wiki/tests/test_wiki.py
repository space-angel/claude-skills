"""bandit-wiki wiki.py 테스트 (명세 §10).

실행: bandit-wiki 폴더에서 python3 -m unittest discover -s tests -v
모든 테스트는 임시 디렉터리에서 돈다. 시간은 BANDIT_WIKI_NOW, 사람은 BANDIT_WIKI_USER로 고정한다.
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "wiki.py"
FIXTURE = HERE / "fixtures" / "bandit-team-wiki"

_spec = importlib.util.spec_from_file_location("bandit_wiki", SCRIPT)
wiki = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wiki)

T0 = "2026-10-26T10:00:00"


class WikiTestCase(unittest.TestCase):
    areas = "app,booking,notify"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bandit-wiki-test-"))
        self.root = self.tmp / ".wiki"
        self._env = {k: os.environ.get(k) for k in ("BANDIT_WIKI_USER", "BANDIT_WIKI_NOW")}
        code, _out, err = self.cli("init", "--areas", self.areas)
        self.assertEqual(code, 0, err)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- 도우미 ---
    def cli(self, *args, user="도윤", now=T0, stdin=None):
        os.environ["BANDIT_WIKI_USER"] = user
        os.environ["BANDIT_WIKI_NOW"] = now
        out, err = io.StringIO(), io.StringIO()
        old_stdin = sys.stdin
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = wiki.main(["--root", str(self.root)] + [str(a) for a in args])
        finally:
            sys.stdin = old_stdin
        return code, out.getvalue(), err.getvalue()

    def js(self, *args, **kw):
        code, out, err = self.cli("--json", *args, **kw)
        try:
            return code, json.loads(out)
        except ValueError:
            self.fail(f"JSON이 아니에요: {out!r} {err!r}")

    def new(self, did, value, title=None, apply=True, **opts):
        args = ["new", "--id", did, "--title", title or f"{did} 제목", "--value", value, "--reason", "테스트 이유"]
        for k, v in opts.items():
            flag = "--" + k.replace("_", "-")
            if v is True:
                args.append(flag)
            elif v is not None:
                args += [flag, v]
        if apply:
            args.append("--apply")
        return self.cli(*args)

    def change(self, did, base, value, kind="rule", user="도윤", now=T0, extra=()):
        return self.cli("change", did, "--base-version", base, "--value", value, "--reason", f"{value} 로 바꿈",
                        "--kind", kind, "--apply", *extra, user=user, now=now)

    def history(self):
        return wiki.read_jsonl(self.root / "history.jsonl")

    def pending(self, **kw):
        code, data = self.js("pending", **kw)
        self.assertEqual(code, 0)
        return data

    def link(self, issue, did, assignee="서아", status="in_progress", now=T0):
        args = ["link", issue, did, "--title", f"{issue} 작업", "--status", status, "--apply"]
        if assignee:
            args += ["--assignee", assignee]
        code, _o, err = self.cli(*args, now=now)
        self.assertEqual(code, 0, err)

    def touch(self, rel):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# §5 쓰기 시점 검사
# ---------------------------------------------------------------------------


class TestValidation(WikiTestCase):
    def test_bad_id_and_unknown_area(self):
        code, _o, err = self.new("App.Notify", "값이다")
        self.assertEqual(code, 1)
        self.assertIn("VALIDATION_FAILED", err)
        self.assertIn("BAD_ID", err)
        self.assertIn("다음에 할 일", err)
        code, _o, err = self.new("pay.card.limit", "값이다")
        self.assertEqual(code, 1)
        self.assertIn("NEW_AREA", err)

    def test_required_fields_reported_together(self):
        (self.root / "decisions" / "app.md").write_text(
            "# app\n\n### app.screen.dark\n- 제목: 어두운 화면을 지원한다\n- 값: 앱은 어두운 화면을 지원한다\n- 항상 적용: 아니오\n- 상태: 사용\n",
            encoding="utf-8")
        code, data = self.js("check", "app.screen.dark")
        self.assertEqual(code, 1)
        errs = data["decisions"][0]["errors"]
        missing = [e for e in errs if e["code"] == "MISSING_FIELD"]
        self.assertEqual(len(missing), 1, "빠진 칸은 한 번에 모아 보고해야 해요")
        self.assertEqual(missing[0]["fields"], ["이유", "버전"])

    def test_missing_cli_field_is_usage_error(self):
        code, _o, err = self.cli("new", "--id", "app.a.b", "--title", "t", "--value", "v")
        self.assertEqual(code, 2)
        self.assertIn("USAGE", err)

    def test_title_40_chars(self):
        ok_title = "가" * 40
        code, _o, err = self.new("app.title.ok", "값은 하나다", title=ok_title)
        self.assertEqual(code, 0, err)
        code, _o, err = self.new("app.title.long", "값은 둘이다", title="가" * 41)
        self.assertEqual(code, 1)
        self.assertIn("TITLE_TOO_LONG", err)

    def test_always_on_eleventh_rejected(self):
        for i in range(10):
            code, _o, err = self.new(f"app.rule.r{i}", f"규칙 {i}번은 서로 다르다 {'가나다라마바사아자차'[i] * 5}", always_on=True)
            self.assertEqual(code, 0, err)
        code, _o, err = self.new("app.rule.eleventh", "열한 번째 규칙이다", always_on=True)
        self.assertEqual(code, 1)
        self.assertIn("ALWAYS_ON_LIMIT", err)
        code, _o, err = self.new("app.rule.eleventh", "열한 번째 규칙이다")
        self.assertEqual(code, 0, err)

    def test_locked_rejects_ai(self):
        self.new("app.brand.color", "앱의 기본 색은 남색이다", lock="yes")
        code, _o, err = self.cli("change", "app.brand.color", "--base-version", 1, "--value", "앱의 기본 색은 초록이다",
                                 "--reason", "시안 변경", "--kind", "rule", "--actor", "ai", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("STANDARD_LOCKED", err)
        code, _o, err = self.cli("change", "app.brand.color", "--base-version", 1, "--value", "앱의 기본 색은 초록이다",
                                 "--reason", "시안 변경", "--kind", "rule", "--actor", "human", "--apply")
        self.assertEqual(code, 0, err)

    def test_ai_cannot_set_lock(self):
        code, _o, err = self.cli("new", "--id", "app.a.b", "--title", "t", "--value", "v", "--reason", "r",
                                 "--lock", "yes", "--actor", "ai")
        self.assertEqual(code, 1)
        self.assertIn("STANDARD_LOCKED", err)

    def test_version_conflict(self):
        self.new("app.list.size", "목록은 한 번에 20개를 보여 준다")
        self.change("app.list.size", 1, "목록은 한 번에 30개를 보여 준다")
        code, _o, err = self.change("app.list.size", 1, "목록은 한 번에 50개를 보여 준다")
        self.assertEqual(code, 1)
        self.assertIn("VERSION_CONFLICT", err)
        self.assertIn("--base-version 2", err)

    def test_no_change(self):
        self.new("app.list.size", "목록은 한 번에 20개를 보여 준다")
        code, _o, err = self.change("app.list.size", 1, "목록은  한 번에 20개를 보여 준다.")
        self.assertEqual(code, 1)
        self.assertIn("NO_CHANGE", err)
        self.assertEqual(len(self.history()), 1)

    def test_kind_required(self):
        self.new("app.list.size", "목록은 한 번에 20개를 보여 준다")
        code, _o, err = self.cli("change", "app.list.size", "--base-version", 1, "--value", "목록은 30개", "--reason", "r")
        self.assertEqual(code, 1)
        self.assertIn("KIND_REQUIRED", err)
        self.assertIn("문구만 바꿨나요, 규칙을 바꿨나요?", err)

    def test_deprecated_cannot_change(self):
        self.new("app.list.size", "목록은 한 번에 20개를 보여 준다")
        self.new("app.list.paging", "목록은 페이지 없이 계속 불러온다")
        code, _o, err = self.cli("deprecate", "app.list.size", "--reason", "합침", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("REPLACED_BY_MISSING", err)
        code, _o, err = self.cli("deprecate", "app.list.size", "--replaced-by", "app.list.paging", "--reason", "합침", "--apply")
        self.assertEqual(code, 0, err)
        code, _o, err = self.change("app.list.size", 2, "목록은 10개")
        self.assertEqual(code, 1)
        self.assertIn("DEPRECATED", err)
        self.assertIn("app.list.paging", err)

    def test_review_date_required(self):
        code, _o, err = self.new("app.launch.beta", "베타는 11/30까지만 연다")
        self.assertEqual(code, 1)
        self.assertIn("REVIEW_DATE_REQUIRED", err)
        code, _o, err = self.new("app.launch.beta", "베타는 11/30까지만 연다", review_by="2026-11-30")
        self.assertEqual(code, 0, err)

    def test_warnings_vague_multi_duplicate_id_mismatch(self):
        self.new("notify.channel.list", "예약 알림은 앱 푸시와 문자로 보낸다", title="예약 알림 채널은 세 곳이다")
        code, out = self.js("new", "--id", "notify.channel.three", "--title", "알림 채널은 세 곳이다",
                            "--value", "예약 알림은 앱 푸시와 문자 두 곳으로 보내고 가능하면 그리고 메일도 쓴다", "--reason", "r")
        self.assertEqual(code, 0)
        codes = {w["code"] for w in out["warnings"]}
        self.assertTrue({"VAGUE_WORD", "MULTI_RULE", "DUPLICATE_SUSPECT", "ID_VALUE_MISMATCH"} <= codes, codes)
        self.assertEqual(self.history()[-1]["id"], "notify.channel.list", "미리보기는 저장하지 않아요")


# ---------------------------------------------------------------------------
# §3 정규화·되돌림, §9 CHANGELOG
# ---------------------------------------------------------------------------


class TestHistoryAndChangelog(WikiTestCase):
    def test_revert_normalization(self):
        self.new("notify.daily.max", "알림은 하루에 4개까지 보낸다")
        self.change("notify.daily.max", 1, "알림은 하루에 5개까지 보낸다")
        code, _o, err = self.change("notify.daily.max", 2, "알림은 하루에 ４ 개까지 보낸다.")  # 전각·공백·마침표
        self.assertEqual(code, 0, err)
        last = self.history()[-1]
        self.assertTrue(last["is_revert"])
        self.assertEqual(last["reverted_to"], 1)
        self.assertEqual(last["change_kind"], "revert")
        cl = (self.root / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()[-1]
        self.assertTrue(cl.endswith("(v1로 되돌림) | AI 대화"), cl)

    def test_revert_command(self):
        self.new("notify.daily.max", "알림은 하루에 4개까지 보낸다")
        self.change("notify.daily.max", 1, "알림은 하루에 5개까지 보낸다")
        code, _o, err = self.cli("revert", "notify.daily.max", "--to-version", 1, "--reason", "5개는 너무 많다는 문의", "--apply")
        self.assertEqual(code, 0, err)
        last = self.history()[-1]
        self.assertEqual((last["version"], last["value"], last["reverted_to"]), (3, "알림은 하루에 4개까지 보낸다", 1))

    def test_changelog_line_formats(self):
        self.new("app.copy.pipe", "구분자는 A|B 형식으로 쓴다", title="구분자는 A|B다")
        self.new("app.copy.new", "구분자는 쉼표로 쓴다")
        self.cli("change", "app.copy.new", "--base-version", 1, "--value", "구분자는 쉼표(,)로 쓴다", "--reason", "괄호 추가",
                 "--kind", "wording", "--apply")
        self.cli("deprecate", "app.copy.pipe", "--replaced-by", "app.copy.new", "--reason", "하나로|합침", "--apply")
        lines = [l for l in (self.root / "CHANGELOG.md").read_text(encoding="utf-8").splitlines() if l.startswith("2026")]
        self.assertEqual(lines[0], "2026-10-26 10:00 | 도윤 | app.copy.pipe new→1 | (없음) → 구분자는 A/B 형식으로 쓴다 | 테스트 이유 | AI 대화")
        self.assertEqual(lines[2], "2026-10-26 10:00 | 도윤 | app.copy.new 1→2 | 구분자는 쉼표로 쓴다 → 구분자는 쉼표(,)로 쓴다 | [문구] 괄호 추가 | AI 대화")
        self.assertEqual(lines[3], "2026-10-26 10:00 | 도윤 | app.copy.pipe 1→2 | 구분자는 A/B 형식으로 쓴다 → 폐기(대체: app.copy.new) | 하나로/합침 | AI 대화")
        for l in lines:
            self.assertEqual(len(l.split(" | ")), 6)

    def test_timezone_from_config(self):
        cfg = json.loads((self.root / "config.json").read_text(encoding="utf-8"))
        cfg["timezone"] = "UTC"
        (self.root / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        self.cli("new", "--id", "app.a.b", "--title", "t", "--value", "v", "--reason", "r", "--apply", now="2026-10-26T10:00:00+09:00")
        self.assertEqual(self.history()[0]["at"], "2026-10-26T01:00:00+00:00")
        self.assertIn("2026-10-26 01:00 |", (self.root / "CHANGELOG.md").read_text(encoding="utf-8"))

    def test_append_only_history(self):
        self.new("app.a.one", "첫 번째 값이다")
        before = (self.root / "history.jsonl").read_bytes()
        self.change("app.a.one", 1, "두 번째 값이다")
        self.new("app.a.two", "다른 결정이다")
        after = (self.root / "history.jsonl").read_bytes()
        self.assertTrue(after.startswith(before))
        self.assertEqual(len(after.splitlines()), 3)


# ---------------------------------------------------------------------------
# §7 확인 필요
# ---------------------------------------------------------------------------


class TestPending(WikiTestCase):
    def setUp(self):
        super().setUp()
        self.new("booking.cancel.window", "예약 취소는 이용 24시간 전까지만 받는다", interpretation="최대치다")

    def items(self, **kw):
        return self.pending(**kw)["items"]

    def skipped(self):
        return {(s["issue"], s["reason"]) for s in self.pending()["skipped"]}

    def test_wording_does_not_create_pending(self):
        self.link("BK-1", "booking.cancel.window")
        self.change("booking.cancel.window", 1, "예약 취소는 이용 시작 24시간 전까지만 받는다", kind="wording")
        self.assertEqual(self.items(), [])
        self.assertIn(("BK-1", "wording_or_self"), self.skipped())

    def test_rule1_canceled_skipped(self):
        self.link("BK-1", "booking.cancel.window", status="canceled")
        self.change("booking.cancel.window", 1, "예약 취소는 이용 12시간 전까지만 받는다")
        self.assertEqual(self.items(), [])
        self.assertIn(("BK-1", "skip_canceled"), self.skipped())

    def test_rule2_no_assignee_skipped(self):
        self.link("BK-1", "booking.cancel.window", assignee=None)
        self.change("booking.cancel.window", 1, "예약 취소는 이용 12시간 전까지만 받는다")
        self.assertEqual(self.items(), [])
        self.assertIn(("BK-1", "no_assignee"), self.skipped())

    def test_rule3_seen_version_is_max_of_ack_and_link(self):
        self.link("BK-1", "booking.cancel.window")
        self.change("booking.cancel.window", 1, "예약 취소는 이용 12시간 전까지만 받는다")
        self.assertEqual(self.items()[0]["from_version"], 1)  # 연결 버전
        code, _o, err = self.cli("ack", "BK-1", "booking.cancel.window", "--version", 2, "--affected", "no",
                                 "--reason", "취소 화면은 아직 손대지 않음", "--apply", user="서아")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.items(), [])
        self.change("booking.cancel.window", 2, "예약 취소는 이용 6시간 전까지만 받는다")
        it = self.items()[0]
        self.assertEqual((it["from_version"], it["to_version"]), (2, 3))  # ack 버전
        self.link("BK-2", "booking.cancel.window")  # v3에 연결
        self.assertEqual([i["issue"] for i in self.items()], ["BK-1"])

    def test_rule4_author_is_assignee(self):
        self.link("BK-1", "booking.cancel.window", assignee="도윤")
        self.change("booking.cancel.window", 1, "예약 취소는 이용 12시간 전까지만 받는다", user="도윤")
        self.assertEqual(self.items(), [])
        self.assertIn(("BK-1", "wording_or_self"), self.skipped())

    def test_rule5_closed_by_revert(self):
        self.link("BK-1", "booking.cancel.window")
        self.change("booking.cancel.window", 1, "예약 취소는 이용 12시간 전까지만 받는다")
        self.assertEqual(len(self.items()), 1)
        self.change("booking.cancel.window", 2, "예약 취소는 이용 24시간 전까지만 받는다")
        self.assertEqual(self.items(), [])
        self.assertIn(("BK-1", "closed_by_revert"), self.skipped())

    def test_rule6_merged_versions_done_included_and_renotify(self):
        self.link("BK-1", "booking.cancel.window", status="done")
        self.change("booking.cancel.window", 1, "예약 취소는 이용 12시간 전까지만 받는다", now="2026-10-26T11:00:00")
        self.change("booking.cancel.window", 2, "예약 취소는 이용 6시간 전까지만 받는다", user="하준", now="2026-10-26T12:00:00")
        items = self.items()
        self.assertEqual(len(items), 1, "중간 버전은 하나로 묶어요")
        it = items[0]
        self.assertEqual((it["from_version"], it["to_version"]), (1, 3))
        self.assertEqual(it["from_value"], "예약 취소는 이용 24시간 전까지만 받는다")
        self.assertEqual(it["to_value"], "예약 취소는 이용 6시간 전까지만 받는다")
        self.assertEqual((it["by"], it["assignee"], it["issue_status"]), ("하준", "서아", "done"))
        self.cli("ack", "BK-1", "booking.cancel.window", "--version", 3, "--affected", "yes", "--known", "no", "--apply", user="서아")
        self.assertEqual(self.items(), [])
        self.change("booking.cancel.window", 3, "예약 취소는 이용 3시간 전까지만 받는다")
        self.assertEqual(self.items()[0]["from_version"], 3, "답한 뒤 또 바뀌면 새로 생겨요")

    def test_deprecate_creates_pending(self):
        self.new("booking.cancel.policy", "취소 규칙은 매장마다 정한다")
        self.link("BK-1", "booking.cancel.window")
        self.cli("deprecate", "booking.cancel.window", "--replaced-by", "booking.cancel.policy", "--reason", "매장별로", "--apply")
        it = self.items()[0]
        self.assertEqual(it["to_value"], "폐기(대체: booking.cancel.policy)")

    def test_unlinked_excluded(self):
        self.link("BK-1", "booking.cancel.window")
        code, _o, err = self.cli("unlink", "BK-1", "booking.cancel.window", "--reason", "잘못 연결", "--apply")
        self.assertEqual(code, 0, err)
        self.change("booking.cancel.window", 1, "예약 취소는 이용 12시간 전까지만 받는다")
        self.assertEqual(self.items(), [])

    def test_relink_keeps_existing_links(self):
        self.new("booking.slot.unit", "예약 시간은 30분 단위로 나눈다")
        self.link("BK-1", "booking.cancel.window")
        before = (self.root / "links.jsonl").read_bytes()
        code, out, _e = self.cli("link", "BK-1", "booking.slot.unit", "--apply")
        self.assertEqual(code, 0)
        self.assertIn("기존 연결은 그대로 둬요: booking.cancel.window", out)
        self.assertTrue((self.root / "links.jsonl").read_bytes().startswith(before))
        self.change("booking.cancel.window", 1, "예약 취소는 이용 12시간 전까지만 받는다")
        self.assertEqual([i["id"] for i in self.items()], ["booking.cancel.window"])

    def test_assignee_change_moves_pending(self):
        self.link("BK-1", "booking.cancel.window")
        self.change("booking.cancel.window", 1, "예약 취소는 이용 12시간 전까지만 받는다")
        self.cli("issue-update", "BK-1", "--assignee", "하준", "--apply")
        self.assertEqual(self.items()[0]["assignee"], "하준")
        self.assertEqual(self.pending()["count"], 1)

    def test_ack_validation(self):
        self.link("BK-1", "booking.cancel.window")
        self.change("booking.cancel.window", 1, "예약 취소는 이용 12시간 전까지만 받는다")
        code, _o, err = self.cli("ack", "BK-1", "booking.cancel.window", "--version", 2, "--affected", "yes", "--apply", user="서아")
        self.assertEqual(code, 1)
        self.assertIn("--known", err)
        code, _o, err = self.cli("ack", "BK-1", "booking.cancel.window", "--version", 2, "--affected", "no", "--apply", user="서아")
        self.assertEqual(code, 1)
        code, _o, err = self.cli("ack", "BK-1", "booking.cancel.window", "--version", 2, "--affected", "no",
                                 "--reason", "가" * 101, "--apply", user="서아")
        self.assertEqual(code, 1)
        code, out, _e = self.cli("ack", "BK-1", "booking.cancel.window", "--version", 2, "--affected", "unsure", "--apply", user="서아")
        self.assertEqual(code, 0)
        self.assertEqual((self.root / "acks.jsonl").read_text(encoding="utf-8"), "")
        code, _o, err = self.cli("ack", "BK-1", "booking.cancel.window", "--version", 1, "--affected", "yes", "--known", "yes", "--apply", user="서아")
        self.assertEqual(code, 1)
        self.assertIn("VERSION_CONFLICT", err)

    def test_preview_shows_impact(self):
        self.link("BK-1", "booking.cancel.window")
        code, out, _e = self.cli("change", "booking.cancel.window", "--base-version", 1, "--value", "예약 취소는 이용 12시간 전까지만 받는다",
                                 "--reason", "r", "--kind", "rule")
        self.assertEqual(code, 0)
        self.assertIn("연결된 이슈 1건, 확인 요청 1건 (담당자: 서아)", out)
        code, data = self.js("impact", "booking.cancel.window", "--value", "예약 취소는 이용 24시간 전까지만 받는다.")
        self.assertEqual(data["checks"], 1)
        self.assertTrue(data["no_change"])


# ---------------------------------------------------------------------------
# 32자 사건, scope, lint
# ---------------------------------------------------------------------------


class TestScopeAndLint(WikiTestCase):
    def test_32_char_incident(self):
        self.touch("apps/web/src/notify/title.ts")
        code, data = self.js("new", "--id", "app.notify.title-length", "--title", "알림 제목은 40자 이하다",
                             "--value", "운영체제 알림 제목은 공백 포함 40자 이하로 쓴다", "--reason", "잠금 화면에서 잘리지 않게 한다",
                             "--scope-code", "packages/app/src/notify/**")
        self.assertEqual(code, 0)
        warns = {w["code"]: w for w in data["warnings"]}
        self.assertIn("AMBIGUOUS_COMPARATIVE", warns)
        self.assertIn("최대치인가요, 맞춰야 하는 값인가요?", warns["AMBIGUOUS_COMPARATIVE"]["message"])
        self.assertIn("SCOPE_PATH_MISSING", warns)
        self.assertIn("apps/web/src/notify/**", warns["SCOPE_PATH_MISSING"]["suggestions"])
        code, data = self.js("new", "--id", "app.notify.title-length", "--title", "알림 제목은 40자 이하다",
                             "--value", "운영체제 알림 제목은 공백 포함 40자 이하로 쓴다", "--reason", "잠금 화면에서 잘리지 않게 한다",
                             "--scope-code", "apps/web/src/notify/**",
                             "--interpretation", "40자는 최대치다. 32자에서 자르는 기존 코드는 위반이 아니다", "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(data["warnings"], [])
        code, out, _e = self.cli("for-path", str(self.tmp / "apps/web/src/notify/title.ts"))
        self.assertIn("app.notify.title-length (v1)", out)
        self.assertIn("해석: 40자는 최대치다", out)

    def test_lint_29_of_40_broken(self):
        for i in range(11):
            self.touch(f"apps/web/src/m{i}/index.ts")
        n = 0
        for d in range(4):
            globs = []
            for _ in range(10):
                globs.append(f"apps/web/src/m{n}/**" if n < 11 else f"packages/old/m{n}/**")
                n += 1
            code, _o, err = self.new(f"app.module.group-{d}", f"모듈 묶음 {d}번은 규칙 {d * 7}을 따른다 {'가나다라'[d] * 6}",
                                     scope_code=",".join(globs))
            self.assertEqual(code, 0, err)
        code, data = self.js("lint")
        self.assertEqual(code, 0, "깨진 경로는 경고예요")
        summary = [w for w in data["warnings"] if w["code"] == "SCOPE_SUMMARY"][0]
        self.assertEqual((summary["total"], summary["broken"]), (40, 29))
        self.assertIn("40개 중 29개", summary["message"])
        self.assertEqual(sum(1 for w in data["warnings"] if w["code"] == "SCOPE_PATH_MISSING"), 29)

    def test_lint_review_overdue_orphan_coverage(self):
        self.new("app.launch.beta", "베타는 11/30까지만 연다", review_by="2026-10-01")
        self.new("app.list.size", "목록은 한 번에 20개를 보여 준다")
        self.link("BK-1", "app.list.size")
        self.cli("link", "BK-2", "app.list.size", "--title", "다른 작업", "--status", "in_progress", "--apply")
        self.cli("unlink", "BK-2", "app.list.size", "--reason", "잘못", "--apply")
        code, data = self.js("lint")
        codes = {x["code"] for x in data["warnings"] + data["info"]}
        self.assertIn("REVIEW_OVERDUE", codes)
        orphan = [x for x in data["info"] if x["code"] == "ORPHAN"][0]
        self.assertEqual(orphan["ids"], ["app.launch.beta"])
        cov = [x for x in data["info"] if x["code"] == "LINK_COVERAGE"][0]
        self.assertEqual((cov["total"], cov["unlinked"]), (2, 1))

    def test_generated_drift_detected_and_fixed(self):
        self.new("app.list.size", "목록은 한 번에 20개를 보여 준다")
        code, _o, _e = self.cli("sync", "--check")
        self.assertEqual(code, 0)
        idx = self.root / "INDEX.md"
        idx.write_text(idx.read_text(encoding="utf-8") + "\n손으로 쓴 줄\n", encoding="utf-8")
        code, out, _e = self.cli("sync", "--check")
        self.assertEqual(code, 1)
        self.assertIn(".wiki/INDEX.md", out)
        code, data = self.js("lint")
        self.assertIn("GENERATED_DRIFT", {w["code"] for w in data["warnings"]})
        code, data = self.js("lint", "--fix")
        self.assertNotIn("GENERATED_DRIFT", {w["code"] for w in data["warnings"]})
        self.assertEqual(self.cli("sync", "--check")[0], 0)

    def test_for_path_hook_stdin(self):
        self.new("booking.slot.unit", "예약 시간은 30분 단위로 나눈다", scope_code="src/booking/**")
        payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(self.tmp / "src/booking/slot.ts")}})
        code, out, _e = self.cli("for-path", "--hook", stdin=payload)
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("booking.slot.unit", data["hookSpecificOutput"]["additionalContext"])
        code, out, _e = self.cli("for-path", "--hook", stdin=json.dumps({"tool_input": {"file_path": "/elsewhere/x.ts"}}))
        self.assertEqual((code, out), (0, ""))
        shutil.rmtree(self.root)
        self.assertEqual(self.cli("for-path", "--hook", stdin=payload), (0, "", ""))
        self.assertEqual(self.cli("for-path", "--hook", "--bad-flag", stdin=payload)[0], 0)


# ---------------------------------------------------------------------------
# HAND_EDIT, 내보내기
# ---------------------------------------------------------------------------


class TestHandEditAndExports(WikiTestCase):
    def test_hand_edit_and_adopt(self):
        self.new("booking.slot.unit", "예약 시간은 30분 단위로 나눈다")
        self.new("booking.slot.other", "예약 칸은 하루 단위로 보여 준다")
        path = self.root / "decisions" / "booking.md"
        text = path.read_text(encoding="utf-8")
        old = "- 값: 예약 시간은 30분 단위로 나눈다\n- 이유: 테스트 이유"
        self.assertIn(old, text)
        path.write_text(text.replace(old, "- 값: 예약 시간은 15분 단위로 나눈다\n- 이유: 짧은 시술이 늘었다"), encoding="utf-8")
        code, data = self.js("check")
        self.assertEqual(code, 1)
        he = [e for d in data["decisions"] for e in d["errors"] if e["code"] == "HAND_EDIT"]
        self.assertEqual(len(he), 1)
        self.assertIn("값", he[0]["message"])
        code, _o, err = self.change("booking.slot.other", 1, "예약 칸은 주 단위로 보여 준다")
        self.assertEqual(code, 1)
        self.assertIn("HAND_EDIT", err)
        code, _o, err = self.cli("adopt", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("KIND_REQUIRED", err)
        code, _o, err = self.cli("adopt", "booking.slot.unit", "--kind", "rule", "--apply")
        self.assertEqual(code, 0, err)
        last = self.history()[-1]
        self.assertEqual((last["id"], last["version"], last["value"], last["reason"]),
                         ("booking.slot.unit", 2, "예약 시간은 15분 단위로 나눈다", "짧은 시술이 늘었다"))
        self.assertEqual(self.cli("check")[0], 0)
        self.assertIn("booking.slot.unit 1→2", (self.root / "CHANGELOG.md").read_text(encoding="utf-8"))

    def test_adopt_new_block_and_refuse_delete(self):
        self.new("booking.slot.unit", "예약 시간은 30분 단위로 나눈다")
        path = self.root / "decisions" / "booking.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n### booking.slot.max\n- 제목: 하루 예약은 열 칸까지다\n- 값: 손님 한 명은 하루에 예약 칸을 최대 열 개까지 잡는다\n"
                        "- 이유: 독점을 막는다\n- 항상 적용: 아니오\n- 상태: 사용\n- 버전: 1\n", encoding="utf-8")
        code, _o, err = self.cli("adopt", "--apply")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.history()[-1]["change_kind"], "addition")
        text = path.read_text(encoding="utf-8")
        start = text.index("### booking.slot.max")
        path.write_text(text[:start], encoding="utf-8")
        code, _o, err = self.cli("adopt", "--apply")
        self.assertEqual(code, 1)
        self.assertIn("deprecate", err)

    def test_claude_md_outside_block_preserved(self):
        claude = self.tmp / "CLAUDE.md"
        before, after = "# 우리 프로젝트\n\n직접 쓴 안내예요.\n\n", "\n\n## 직접 쓴 꼬리\n- 지우면 안 돼요\n"
        block = claude.read_text(encoding="utf-8").strip("\n")
        claude.write_text(before + block + after, encoding="utf-8")
        self.new("app.copy.plain", "설명은 쉬운 말로 쓴다", always_on=True, interpretation="개발 용어는 괄호로 푼다")
        text = claude.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(before))
        self.assertTrue(text.endswith(after))
        self.assertIn("`app.copy.plain` (v1) 설명은 쉬운 말로 쓴다", text)
        self.assertIn("해석: 개발 용어는 괄호로 푼다", text)
        self.assertEqual(text.count(wiki.BLOCK_START), 1)

    def test_claude_md_created_only_when_exported(self):
        cfg = json.loads((self.root / "config.json").read_text(encoding="utf-8"))
        cfg["exports"] = ["claude-rules"]
        (self.root / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        (self.tmp / "AGENTS.md").unlink()
        (self.tmp / "CLAUDE.md").write_text("내 파일\n", encoding="utf-8")
        self.new("app.copy.plain", "설명은 쉬운 말로 쓴다", always_on=True)
        self.assertFalse((self.tmp / "AGENTS.md").exists())
        self.assertEqual((self.tmp / "CLAUDE.md").read_text(encoding="utf-8"), "내 파일\n")

    def test_claude_rules_paths_export(self):
        self.new("booking.slot.unit", "예약 시간은 30분 단위로 나눈다", scope_code="src/booking/slot/**,src/booking/api/*.ts")
        self.new("booking.cancel.window", "예약 취소는 이용 24시간 전까지 받는다", scope_code="src/booking/cancel/**", interpretation="최대치")
        self.new("booking.copy.tone", "예약 문구는 존댓말로 쓴다")
        rule = self.tmp / ".claude" / "rules" / "bandit-booking.md"
        text = rule.read_text(encoding="utf-8")
        self.assertTrue(text.startswith('---\npaths:\n  - "src/booking/api/*.ts"\n  - "src/booking/cancel/**"\n  - "src/booking/slot/**"\n---\n'), text)
        self.assertIn(wiki.GENERATED_MARK, text)
        self.assertNotIn("booking.copy.tone", text, "scope.code가 없는 결정은 빠져요")
        self.cli("deprecate", "booking.slot.unit", "--replaced-by", "booking.copy.tone", "--reason", "합침", "--apply")
        self.cli("deprecate", "booking.cancel.window", "--replaced-by", "booking.copy.tone", "--reason", "합침", "--apply")
        self.assertFalse(rule.exists(), "결정이 없어진 영역의 규칙 파일은 지워요")

    def test_cursor_export(self):
        cfg = json.loads((self.root / "config.json").read_text(encoding="utf-8"))
        cfg["exports"] = ["cursor"]
        (self.root / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        self.new("booking.slot.unit", "예약 시간은 30분 단위로 나눈다", scope_code="src/booking/**", always_on=True)
        mdc = (self.tmp / ".cursor" / "rules" / "bandit-booking.mdc").read_text(encoding="utf-8")
        self.assertIn("globs: src/booking/**\nalwaysApply: false", mdc)
        always = (self.tmp / ".cursor" / "rules" / "bandit-always.mdc").read_text(encoding="utf-8")
        self.assertIn("alwaysApply: true", always)


# ---------------------------------------------------------------------------
# import-bandit, seen, metrics
# ---------------------------------------------------------------------------


class TestImportSeenMetrics(WikiTestCase):
    areas = "booking"

    def test_import_bandit_round_trip(self):
        code, out, _e = self.cli("import-bandit", FIXTURE)
        self.assertEqual(code, 0)
        self.assertIn("결정 5개, 버전 11개", out)
        self.assertEqual(self.history(), [], "미리보기는 쓰지 않아요")
        code, data = self.js("import-bandit", FIXTURE, "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(data["new_areas"], ["notify"])
        src_lines = [l for l in (FIXTURE / "CHANGELOG.md").read_text(encoding="utf-8").splitlines() if l[:2] == "20"]
        out_lines = [l for l in (self.root / "CHANGELOG.md").read_text(encoding="utf-8").splitlines() if l[:2] == "20"]
        self.assertEqual(out_lines, src_lines)
        for src, area in (("예약.md", "booking"), ("알림.md", "notify")):
            _p, a, _o = wiki.parse_decision_text((FIXTURE / src).read_text(encoding="utf-8"))
            _p, b, _o = wiki.parse_decision_text((self.root / "decisions" / f"{area}.md").read_text(encoding="utf-8"))
            self.assertEqual([wiki.block_to_state(x)[0] for x in a], [wiki.block_to_state(x)[0] for x in b])
        hist = self.history()
        self.assertTrue(all(r["source"] == "import" for r in hist))
        rev = [r for r in hist if r["id"] == "notify.reminder.time"][-1]
        self.assertEqual((rev["is_revert"], rev["reverted_to"]), (True, 1))
        self.assertEqual(self.cli("check")[0], 0)
        self.assertEqual(self.cli("sync", "--check")[0], 0)
        code, _o, err = self.cli("import-bandit", FIXTURE, "--apply")
        self.assertEqual(code, 1)
        self.assertIn("IMPORT_NOT_EMPTY", err)
        # 가져온 뒤 바꾸기: 잠금은 그대로
        code, _o, err = self.cli("change", "notify.channel.two", "--base-version", 2, "--value", "x", "--reason", "r",
                                 "--kind", "rule", "--actor", "ai")
        self.assertIn("STANDARD_LOCKED", err)

    def test_seen_output(self):
        self.new("booking.slot.unit", "예약 시간은 30분 단위로 나눈다")
        code, out, _e = self.cli("seen")
        self.assertIn("처음 보는 위키", out)
        self.cli("seen", "--mark")
        code, out, _e = self.cli("seen")
        self.assertEqual((code, out), (0, ""), "바뀐 게 없으면 아무것도 출력하지 않아요")
        self.link("BK-1", "booking.slot.unit", assignee="서아")
        self.change("booking.slot.unit", 1, "예약 시간은 15분 단위로 나눈다", user="도윤")
        code, out, _e = self.cli("seen", user="서아")
        self.assertIn("마지막으로 본 뒤 바뀐 결정 1개", out)
        self.assertIn("booking.slot.unit v1→v2: 예약 시간은 15분 단위로 나눈다 (도윤)", out)
        self.assertIn("내 확인 필요 1건", out)
        self.cli("seen", "--mark", user="서아")
        code, out, _e = self.cli("seen", user="서아")
        self.assertIn("내 확인 필요 1건", out)
        self.assertNotIn("바뀐 결정", out)

    def test_metrics_funnel(self):
        self.new("booking.slot.unit", "예약 시간은 30분 단위로 나눈다")
        self.link("BK-1", "booking.slot.unit", assignee="서아")
        self.link("BK-2", "booking.slot.unit", assignee="하준")
        self.link("BK-3", "booking.slot.unit", assignee="민지", status="todo")
        self.cli("link", "BK-4", "booking.slot.unit", "--title", "t", "--status", "in_progress", "--apply")
        self.cli("unlink", "BK-4", "booking.slot.unit", "--reason", "잘못", "--apply")
        self.change("booking.slot.unit", 1, "예약 시간은 15분 단위로 나눈다", now="2026-10-26T11:00:00")
        self.cli("ack", "BK-1", "booking.slot.unit", "--version", 2, "--affected", "yes", "--known", "no", "--apply", user="서아", now="2026-10-26T13:00:00")
        self.cli("ack", "BK-2", "booking.slot.unit", "--version", 2, "--affected", "no", "--reason", "관계없음", "--apply", user="하준", now="2026-10-26T15:00:00")
        code, m = self.js("metrics", "--days", 7, now="2026-10-27T09:00:00")
        self.assertEqual(code, 0)
        self.assertEqual(m["funnel"], {"created": 3, "answered": 2, "affected": 1, "unknown": 1})
        self.assertEqual(m["median_hours_to_answer"], 3.0)
        self.assertEqual(m["people"], {"도윤": 2})
        self.assertEqual(m["coverage"], {"in_progress": 3, "linked": 2})
        code, out, _e = self.cli("metrics", now="2026-10-27T09:00:00")
        self.assertIn("확인 필요 3건 → 답함 3건 중 2건 → 관계있다 2건 중 1건 → 몰랐다 1건 중 1건", out)
        self.assertIn("진행 중 이슈 3건 중 결정과 연결된 이슈 2건", out)

    def test_title_value_number_mismatch_warns(self):
        self.new("booking.slot.unit", "예약 시간은 30분 단위로 나눈다", title="예약 시간 단위는 30분이다")
        code, data = self.js("change", "booking.slot.unit", "--base-version", 1, "--value", "예약 시간은 15분 단위로 나눈다",
                             "--reason", "r", "--kind", "rule")
        self.assertIn("제목에는 숫자 [30]", " ".join(w["message"] for w in data["warnings"]))



# ---------------------------------------------------------------------------
# 시나리오 테스트(가상 펫시터 예약 팀)에서 나온 회귀 테스트
# ---------------------------------------------------------------------------


class TestScenarioRegressions(WikiTestCase):
    def test_generated_files_keep_umask_and_existing_mode(self):
        # mkstemp 기본 0600 때문에 CLAUDE.md·INDEX.md가 나만 읽는 파일이 되던 문제
        old = os.umask(0o022)
        try:
            self.new("booking.slot.unit", "예약 시간은 30분 단위로 나눈다")
            for rel in (".wiki/INDEX.md", ".wiki/CHANGELOG.md", ".wiki/decisions/booking.md", "CLAUDE.md"):
                self.assertEqual((self.tmp / rel).stat().st_mode & 0o777, 0o644, rel)
            claude = self.tmp / "CLAUDE.md"
            os.chmod(claude, 0o640)
            self.change("booking.slot.unit", 1, "예약 시간은 15분 단위로 나눈다")
            self.assertEqual(claude.stat().st_mode & 0o777, 0o640)
        finally:
            os.umask(old)

    def test_pending_questions_match_skill_and_hint_does_not_prefill(self):
        self.new("booking.slot.unit", "예약 시간은 30분 단위로 나눈다")
        self.link("BK-1", "booking.slot.unit", assignee="서아")
        self.change("booking.slot.unit", 1, "예약 시간은 15분 단위로 나눈다")
        q = self.pending()["questions"]
        self.assertEqual(q["affected"]["question"], "이 변경이 내 이슈와 관계가 있나요?")
        self.assertEqual(q["affected"]["options"], ["관계있다", "관계없다", "잘 모르겠다"])
        self.assertEqual(q["known"]["question"], "이 변경을 이미 알고 있었나요?")
        self.assertEqual(q["known"]["options"], ["알았다", "몰랐다"])
        self.assertEqual(q["reason"]["question"], "왜 관계없나요?")
        skill = (HERE.parent.parent / "bandit-issue-link" / "SKILL.md")
        if skill.exists():
            text = skill.read_text(encoding="utf-8")
            for item in q.values():
                self.assertIn(item["question"], text)
        _c, out, _e = self.cli("pending")
        self.assertNotIn("--affected yes --known no", out)
        self.assertIn("--affected <yes|no>", out)

    def test_interpretation_carried_over_on_value_change_warns(self):
        self.new("booking.cancel.free-window", "무료 취소는 이용 24시간 전까지 받는다", title="무료 취소 기한",
                 interpretation="24시간은 최소 여유다")
        code, data = self.js("change", "booking.cancel.free-window", "--base-version", 1, "--kind", "rule",
                             "--value", "무료 취소는 이용 12시간 전까지 받는다", "--reason", "r")
        self.assertEqual(code, 0)
        self.assertIn("INTERPRETATION_STALE", [w["code"] for w in data["warnings"]])
        code, data = self.js("change", "booking.cancel.free-window", "--base-version", 1, "--kind", "rule",
                             "--value", "무료 취소는 이용 12시간 전까지 받는다", "--reason", "r",
                             "--interpretation", "12시간은 최소 여유다")
        self.assertNotIn("INTERPRETATION_STALE", [w["code"] for w in data["warnings"]])
        # 직접 고친 파일(adopt)도 같은 경고
        path = self.root / "decisions" / "booking.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("이용 24시간 전까지", "이용 6시간 전까지"), encoding="utf-8")
        code, data = self.js("adopt", "booking.cancel.free-window", "--kind", "rule")
        self.assertEqual(code, 0)
        self.assertIn("INTERPRETATION_STALE", [w["code"] for w in data["warnings"]])


if __name__ == "__main__":
    unittest.main()
