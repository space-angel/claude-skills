# Claude Code Skills

PO가 AI와 함께 만든 결과물을 팀에 내보낼 때 필요한 스킬과, 상황에 따라 어떤 스킬을 쓰는지 소개합니다.

AI는 빠르게 초안을 만들지만, 그 초안이 그대로 팀에 나가면 문제가 생깁니다. 이미 뺀 범위가 다시 들어가고, 요약을 거친 숫자가 원본과 어긋나고, 맥락을 모르는 사람은 읽을 수 없는 문서가 됩니다. 이 스킬들의 기본 접근 방식은 **원본을 직접 읽고, 근거를 붙이고, 밖으로 나가기 전에 사람이 확인하는 것**입니다.

## Skills

스킬은 하는 일에 따라 일곱 묶음으로 나뉩니다. 문제 해결 묶음은 직접 만든 제품 문제 해결 프레임워크 MAKER를, 팀 위키 묶음은 팀 결정 공유 서비스 [반딧](https://github.com/AX-PJ3/BANDIT)을 운영하며 확인한 문제를 풀기 위해 스킬로 옮긴 것입니다.

| 묶음 | 스킬 | 만드는 것 | 팀에 직접 쓰는가 |
|---|---|---|---|
| 문제 해결 | [maker-navigator](maker-navigator/) | 상황에 맞는 프레임워크 조합과 실행 기록 | 아니요 |
| | [maker-problem-framing](maker-problem-framing/) | 문제 진술문과 "어떻게 하면 ~할 수 있을까" 질문 | 아니요 |
| | [maker-prioritization](maker-prioritization/) | 순위 목록, MVP 범위, 하지 않을 것 | 아니요 |
| | [maker-experiment-design](maker-experiment-design/) | 실험 계획, 지표 정의서, 판정 기준 | 아니요 |
| 계획 | [hypothesis-framework](hypothesis-framework/) | 검증 가능한 가설 한 문장 | 아니요 |
| | [po-doc-writing](po-doc-writing/) | 기획서·명세·결정 문서·회의록·가이드 | 아니요, 초안만 |
| 팀 위키 | [bandit-wiki](bandit-wiki/) | git 안의 결정 위키, 버전·CHANGELOG·규칙 파일 내보내기 | 승인 후 |
| | [bandit-issue-link](bandit-issue-link/) | 결정과 연결된 이슈, 바뀐 결정의 확인 요청 | 승인 후 |
| 실행 추적 | [linear-sync](linear-sync/) | 실제 상태에 맞춘 이슈, 새 이슈 초안 | 승인 후 |
| | [team-status-report](team-status-report/) | 사람별 리포트, 회의 안건, 태스크 지시 | 아니요 |
| 소통 | [slack-team-post](slack-team-post/) | 붙여 넣을 슬랙 메시지 | 아니요, 보내는 건 사람 |
| | [plain-korean-doc](plain-korean-doc/) | 비개발자도 한 번에 읽는 문서 | 아니요 |
| 기록 | [decision-first-article](decision-first-article/) | 결정이 먼저 나오는 아티클 | 아니요 |
| | [evidence-based-retro](evidence-based-retro/) | 산출물 근거의 회고와 피드백 | 아니요 |
| 품질 | [writer-checker-loop](writer-checker-loop/) | 검사를 통과한 고위험 문서 | 아니요 |
| | [ko-tech-prose](ko-tech-prose/) | 문장 진단과 수정 제안 | 아니요 |
| | [pipeline-evaluator](pipeline-evaluator/) | LLM 생성 질문의 품질 점수 | 아니요 |
| 도구 | [notion-ops](notion-ops/) | 노션 등록·조회·수정 커맨드 | 승인 후 |

## Use Cases

PO의 업무 상황은 다음과 같이 나눌 수 있습니다.

### 무엇이 문제인지 모를 때

증상은 보이는데 어디서부터 손댈지 모르는 상황입니다. 이탈이 늘었거나 같은 CS가 반복되는 경우가 여기에 해당합니다.

사용할 수 있는 스킬: [maker-navigator](maker-navigator/), [maker-problem-framing](maker-problem-framing/)

### 할 일이 너무 많을 때

후보 기능과 백로그가 쌓여 이번에 무엇을 할지 정해야 하는 상황입니다.

사용할 수 있는 스킬: [maker-prioritization](maker-prioritization/)

### 새 아이디어가 생겼을 때

효과가 있을지 모르는 아이디어를 실험할 수 있는 형태로 바꾸는 상황입니다.

사용할 수 있는 스킬: [hypothesis-framework](hypothesis-framework/), [maker-experiment-design](maker-experiment-design/), [po-doc-writing](po-doc-writing/)(검증형 기획서)

### 만들기로 정하고 팀에 넘길 때

디자이너와 개발자가 무엇을 언제까지 만들지, 무엇을 만들지 않을지 알아야 하는 상황입니다.

사용할 수 있는 스킬: [po-doc-writing](po-doc-writing/)(실행형 기획서, 기능 명세), [linear-sync](linear-sync/)(이슈 쪼개기)

### 회의 전날

지금 진행 상황과 이번 회의에서 정할 것을 사람별로 정리하는 상황입니다.

사용할 수 있는 스킬: [team-status-report](team-status-report/)

### 회의가 끝난 직후

정한 것을 남기고, 할 일을 이슈로 옮기고, 팀에 알리는 상황입니다.

사용할 수 있는 스킬: [po-doc-writing](po-doc-writing/)(회의록, 결정 기록), [linear-sync](linear-sync/), [slack-team-post](slack-team-post/)

### 작업은 끝났는데 보드가 따라오지 못할 때

머지된 PR과 이슈 상태가 어긋나 있는 상황입니다.

사용할 수 있는 스킬: [linear-sync](linear-sync/)

### 회의나 대화에서 결정이 나왔을 때

정한 것이 흩어지기 전에, 에이전트가 한 가지로 읽을 수 있는 모양으로 남기는 상황입니다.

사용할 수 있는 스킬: [bandit-wiki](bandit-wiki/)

### 팀 결정이 바뀌었을 때

바뀐 결정이 관련 이슈의 담당자와 각자의 에이전트에게 다음 작업 전에 닿아야 하는 상황입니다.

사용할 수 있는 스킬: [bandit-wiki](bandit-wiki/), [bandit-issue-link](bandit-issue-link/)

### 결정이 필요할 때

선택지와 근거를 정리해 결정권자에게 묻는 상황입니다.

사용할 수 있는 스킬: [po-doc-writing](po-doc-writing/)(결정이 필요한 질문), [slack-team-post](slack-team-post/)(PO 결정 요청)

### 스프린트나 프로젝트가 끝났을 때

무엇이 잘 됐고 무엇을 바꿀지 팀과 돌아보는 상황입니다.

사용할 수 있는 스킬: [evidence-based-retro](evidence-based-retro/), [decision-first-article](decision-first-article/)

### 문서가 어렵다는 말을 들었을 때

용어와 비유 때문에 읽는 사람이 막히는 상황입니다.

사용할 수 있는 스킬: [plain-korean-doc](plain-korean-doc/), [ko-tech-prose](ko-tech-prose/)

### 틀리면 안 되는 문서를 쓸 때

이력서, 지원서, 외부 공개 글처럼 숫자 하나가 틀려도 신뢰를 잃는 상황입니다.

사용할 수 있는 스킬: [writer-checker-loop](writer-checker-loop/)

### 노션에 올리거나 고칠 때

사용할 수 있는 스킬: [notion-ops](notion-ops/)

## 독자에 따른 선택

결과물을 누가 읽는지에 따라 확인의 깊이가 달라집니다.

| 독자 | 확인 수준 | 함께 쓰는 스킬 |
|---|---|---|
| 나 혼자 | 초안이면 충분합니다 | 해당 스킬 하나 |
| 팀 내부 | 근거를 붙이고, 외부 도구에 쓰기 전에 승인합니다 | + [linear-sync](linear-sync/), [notion-ops](notion-ops/) |
| 회사 전체 | 맥락 없는 사람 기준으로 용어를 풀어 씁니다 | + [plain-korean-doc](plain-korean-doc/) |
| 외부 공개 | 숫자를 원본과 다시 대조하고 문장을 점검합니다 | + [ko-tech-prose](ko-tech-prose/), [writer-checker-loop](writer-checker-loop/) |

## 자주 헷갈리는 스킬

| | 이걸 쓰세요 | 이럴 때 |
|---|---|---|
| 결정 남기기 | [po-doc-writing](po-doc-writing/) | 결정의 맥락과 선택지를 사람이 읽을 문서로 남길 때 |
| | [bandit-wiki](bandit-wiki/) | 그 결정을 에이전트가 따를 규칙으로 버전과 함께 남길 때 |
| 회의 정리 | [team-status-report](team-status-report/) | 회의 **전**, 상황을 모아 안건을 만들 때 |
| | [po-doc-writing](po-doc-writing/) | 회의 **후**, 정한 것을 회의록으로 남길 때 |
| 팀에 알리기 | [slack-team-post](slack-team-post/) | 세 줄 안팎의 메시지 |
| | [po-doc-writing](po-doc-writing/) | 링크로 걸어 둘 문서 |
| 글 다듬기 | [plain-korean-doc](plain-korean-doc/) | 비유와 어려운 말을 걷어 낼 때 |
| | [ko-tech-prose](ko-tech-prose/) | 번역체, 긴 문장 같은 문장 단위 문제를 찾을 때 |
| 가설 | [hypothesis-framework](hypothesis-framework/) | 가설이 아직 없을 때 |
| | [maker-experiment-design](maker-experiment-design/) | 가설을 검증할 실험 방식, 표본, 지표를 정할 때 |
| | [po-doc-writing](po-doc-writing/) | 실험 계획을 팀에 공유할 기획서로 쓸 때 |
| 프레임워크 | [maker-navigator](maker-navigator/) | 어떤 프레임워크를 써야 할지 모를 때 |
| | maker-problem-framing 등 | 쓸 프레임워크를 이미 알 때 |

## 한 기능의 흐름

예약 앱에 "예약 시간 변경" 기능을 넣는 가상의 시나리오로 스킬이 이어지는 모습을 설명합니다.

### 1. 시작 단계

"변경이 어려워서 취소 후 재예약하는 사람이 많다"는 관찰에서 시작합니다. [maker-problem-framing](maker-problem-framing/)이 피드백과 퍼널을 묶어 문제 진술문으로 정리하고, [hypothesis-framework](hypothesis-framework/)가 질문을 던져 "변경 버튼을 예약 상세에 두면 재예약 이탈이 줄어든다"는 가설로 좁힙니다.

### 2. 정의 단계

[po-doc-writing](po-doc-writing/)으로 실행형 기획서를 씁니다. [maker-prioritization](maker-prioritization/)으로 후보 기능에서 MVP 범위를 고른 뒤, 하지 않는 것(좌석 업그레이드 변경)과 디자이너·개발자의 완료 조건이 문서 앞쪽에 옵니다. [linear-sync](linear-sync/)가 기획서를 하위 이슈 초안으로 쪼개고, 승인 후 등록합니다.

### 3. 진행 단계

주간 회의 전날 [team-status-report](team-status-report/)가 트래커와 GitHub를 읽고, 이슈 없이 머지된 PR과 위키 기준과 어긋난 작업을 안건으로 올립니다. 회의에서 정한 것은 [bandit-wiki](bandit-wiki/)에 남기고, 값이 바뀐 결정은 [bandit-issue-link](bandit-issue-link/)가 연결된 이슈의 담당자에게 확인을 받습니다. 공지는 [slack-team-post](slack-team-post/)로 씁니다.

### 4. 완료 단계

배포 후 [linear-sync](linear-sync/)가 머지된 PR을 근거로 이슈를 닫고 해결 코멘트를 남깁니다. [evidence-based-retro](evidence-based-retro/)로 팀 회고를 하고, [decision-first-article](decision-first-article/)로 "왜 이렇게 만들었나"를 아티클로 남깁니다.

## 원칙

모든 스킬이 같은 원칙을 따릅니다.

| 원칙 | 설명 |
|---|---|
| 밖으로 나가는 건 사람이 승인합니다 | 이슈 등록, 상태 변경, 슬랙 전송, 노션 업로드는 초안을 먼저 보여 줍니다 |
| 기억이 아니라 산출물에서 씁니다 | 이슈·PR·커밋·위키를 직접 읽고, 근거를 문장 옆에 붙입니다 |
| 숫자는 원본에서 다시 셉니다 | 원본이 없으면 쓰지 않거나 묻습니다 |
| 검사하는 쪽은 고치지 않습니다 | 검사 에이전트에는 쓰기 도구가 없습니다 |
| 주장의 출처를 밝힙니다 | 측정한 것과 사용 기록에서 뽑은 것을 구분해 적습니다 |

## 시작하기

스킬 폴더를 스킬 디렉터리에 복사합니다. 다음 세션부터 Claude가 상황에 맞는 스킬을 꺼내 씁니다.

```bash
cp -r linear-sync team-status-report slack-team-post ~/.claude/skills/
```

팀 위키 묶음은 함께 설치합니다. 저장소에서 `python3 bandit-wiki/scripts/wiki.py init`으로 위키를 만듭니다.

```bash
cp -r bandit-wiki bandit-issue-link ~/.claude/skills/
```

MAKER 문제 해결 묶음은 함께 설치합니다.

```bash
cp -r maker-navigator maker-problem-framing maker-prioritization maker-experiment-design ~/.claude/skills/
```

- 저장소 안의 `.claude/skills/`에 두면 그 프로젝트에서만 동작합니다.
- `writer-checker-loop`는 서브에이전트(Claude Code가 띄우는 보조 에이전트) 정의도 `.claude/agents/`에 복사합니다.
- 스킬마다 필요한 준비는 각 문서의 설치 절에 있습니다.

스킬은 `SKILL.md` 파일이 든 폴더입니다. Claude는 맨 위 `description`을 보고 지금 요청에 이 스킬이 필요한지 판단합니다. 요청이 한국어로 들어오기 때문에 대부분의 `SKILL.md`는 한국어로 썼습니다.

## 기여하기

이슈와 PR을 환영합니다. 사실관계를 바로잡는 경우 실행한 커맨드와 출력을 함께 남겨 주세요.
