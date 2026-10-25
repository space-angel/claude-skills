# bandit-wiki hooks

Claude Code hook 두 개로 "바뀐 결정이 다음 작업 전에 닿게" 해요. 둘 다 **작업을 절대 막지 않아요**: 위키가 없거나, 입력이 이상하거나, 스크립트가 실패해도 종료 코드 0으로 끝나요.

| hook | 언제 | 하는 일 |
|---|---|---|
| `SessionStart` | 세션을 열 때 | `wiki.py seen --hook` — 마지막으로 본 뒤 바뀐 결정과 내 확인 필요 수를 한 번 알려요. 아무것도 없으면 출력하지 않아요 |
| `PreToolUse` (`Edit\|Write\|MultiEdit`) | 파일을 고치기 직전 | `wiki.py for-path --hook` — 그 파일 경로에 적용 범위(scope.code)가 걸린 결정의 값과 해석을 Claude와 사람에게 보여 줘요 |

## 설치

아래 조각을 프로젝트의 `.claude/settings.json`(팀이 같이 쓰면) 또는 `.claude/settings.local.json`(나만 쓰면)에 넣어요. 이미 `hooks`가 있으면 배열에 항목만 더해요.

`<SKILL>`은 이 스킬 폴더 경로로 바꿔요. 예:
- 프로젝트에 넣었으면 `$CLAUDE_PROJECT_DIR/.claude/skills/bandit-wiki`
- 개인 스킬이면 `$HOME/.claude/skills/bandit-wiki`

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"<SKILL>/scripts/wiki.py\" --root \"$CLAUDE_PROJECT_DIR/.wiki\" seen --hook || true",
            "timeout": 10
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"<SKILL>/scripts/wiki.py\" --root \"$CLAUDE_PROJECT_DIR/.wiki\" for-path --hook || true",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

## 어떻게 동작하나요

- **SessionStart**: `seen`은 `.git/bandit-wiki-seen`(git이 추적하지 않는 파일)에 적힌 "마지막으로 본 history 줄 수" 이후의 기록만 봐요. 출력은 그대로 세션 맥락에 들어가요. Claude가 내용을 보여 준 뒤 `wiki.py seen --mark`로 본 것으로 표시해요. `.git`이 없는 폴더에서는 `.wiki/.local/seen.json`을 써요(`init`이 `.wiki/.gitignore`에 넣어 둬요).
- **PreToolUse**: Claude Code가 hook의 표준 입력으로 보내는 JSON에서 `tool_input.file_path`를 읽어요(경로 인자를 주지 않거나 `-`를 주면 stdin을 읽어요). 걸린 결정이 있으면 다음 JSON을 출력해요.

```json
{
  "systemMessage": "[bandit-wiki] apps/web/src/notify/title.ts 에 걸린 팀 결정 1개: …",
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "[bandit-wiki] apps/web/src/notify/title.ts 에 걸린 팀 결정 1개: …"
  }
}
```

`additionalContext`는 Claude에게, `systemMessage`는 사람에게 보여요. 사람에게도 보여 주는 이유: 에이전트가 결정을 다르게 읽었을 때(예: "40자 이하"를 "32자여도 괜찮다"로) 사람이 바로 알아챌 수 있게 하려는 거예요. 걸린 결정이 없으면 아무것도 출력하지 않아요. 허용·거부 결정(`permissionDecision`)은 내지 않으므로 권한 흐름은 그대로예요.

## 손으로 확인하기

```bash
# 세션 시작 알림
python3 <SKILL>/scripts/wiki.py seen

# 파일 하나에 걸린 결정
python3 <SKILL>/scripts/wiki.py for-path apps/web/src/notify/title.ts

# hook 입력 흉내
echo '{"tool_name":"Edit","tool_input":{"file_path":"'"$PWD"'/apps/web/src/notify/title.ts"}}' \
  | python3 <SKILL>/scripts/wiki.py for-path --hook
```

## 주의

- hook 스크립트는 네트워크를 쓰지 않고 `.wiki/` 파일만 읽어요. 쓰는 것은 `seen --mark`를 따로 부를 때뿐이에요.
- hook 동작을 바꿔도 각자 다시 설치할 필요가 없어요. 설정은 스크립트 경로만 가리키고, 내용은 스크립트가 정해요.
- 이름은 `BANDIT_WIKI_USER` 환경 변수나 `git config user.name`으로 정해요. 이슈 담당자 이름과 같아야 "내 확인 필요"가 맞게 세져요. 다르면 `.wiki/config.json`의 `people`에 `{"git 이름": "표시 이름"}`을 넣어요.
