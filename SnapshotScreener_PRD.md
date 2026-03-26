# SnapshotScreener — Product Requirements Document (PRD)

> 버전: 1.0  
> 작성일: 2026-03-26  
> 상태: 파일럿 개발 착수 대기  
> 관련 문서: 공장 장비 UI 자동화 아키텍처 검토 문서, 대표 스냅샷 자동 추출기 설계, SnapshotScreener 방법론 확장

---

## 1. 제품 개요

### 1-1. 제품명

**SnapshotScreener**

- CLI 명령어: `snapshot-screener`
- Python 패키지: `snapshot_screener`
- 실행 바이너리: `snapshot-screener.exe`

### 1-2. 한 줄 정의

공장 장비 UI 조작 스크린샷에서 대표 프레임을 자동 추출하고, 자동화 가능한 반복 패턴의 존재 가능성을 사전 판정하는 CLI 도구.

### 1-3. 제품이 해결하는 문제

공장 장비 UI 자동화 프로젝트에서 수집되는 스크린샷은 하루 약 3,000장/장비 × 1만 대 이상 = 수천만 장 규모이다. 이 전체를 Vision AI에 투입하는 것은 비용·시간 모두 비현실적이다. SnapshotScreener는 Vision AI 투입 전 단계에서 두 가지 필터링을 수행한다.

1. **대표 프레임 추출**: 한 장비의 수천 장 스냅샷에서 업무 흐름을 대표하는 수십 장만 선별
2. **패턴 가능성 사전 판정**: 1만 대 장비 중 자동화 패턴이 존재할 가능성이 높은 장비만 선별

### 1-4. 제품의 위치 (시스템 아키텍처 내)

```
Layer 1 — 엣지 (장비 PC Agent)        [완성, 변경 없음]
Layer 2 — 중앙 수집 (CassandraDB)     [완성, 변경 없음]
Layer 3 — AI 분석 파이프라인           [미완성]
  └─ Step 0: SnapshotScreener  ◀ ◀ ◀  이 제품
  └─ Step 1: fname 파싱 + 조작 시퀀스 재구성
  └─ Step 2: Vision AI UI 요소 인식
  └─ Step 3: 반복 패턴 탐지
  └─ Step 4: 자동화 시나리오 생성
Layer 4 — 관리 포털                    [미완성]
```

SnapshotScreener는 Layer 3의 **Step 0 — 전처리 필터**로서, 이후 Step들의 입력 범위를 좁히는 역할을 한다. Step 1~4와 독립적으로 먼저 개발·검증 가능하다.

### 1-5. 제품이 아닌 것

- Vision AI 그 자체가 아니다 — 이미지의 UI 요소를 인식하지 않는다
- 자동화 시나리오를 생성하지 않는다
- "패턴 있음" 판정 ≠ "자동화 가능" 확정. 최종 판단은 사람이 한다
- 실시간 스트리밍 도구가 아니다 — 배치 분석 도구이다

---

## 2. 핵심 제약 조건

### 2-1. 최우선 제약: 프로덕션 Cassandra 무영향

> **SnapshotScreener의 모든 동작은 프로덕션 Cassandra 클러스터의 정상 운영에 영향을 주지 않아야 한다. 이를 위해 실행 속도가 느려지는 것은 허용한다.**

이 제약은 아래의 모든 요구사항에 우선한다. 구체적 이행 방안:

#### 2-1-1. 읽기 전용 접근

- Cassandra에 대해 **SELECT 쿼리만 허용**한다
- INSERT, UPDATE, DELETE, ALTER, CREATE 등 쓰기/변경 쿼리를 절대 실행하지 않는다
- Cassandra 스키마를 변경하지 않는다 (pHash 컬럼 추가 등 불가)

#### 2-1-2. 쿼리 단위 제어

- 모든 Cassandra 쿼리는 **파티션 키 전체를 지정**하는 포인트 쿼리만 사용한다
  - 허용: `WHERE eqpid = ? AND year = ? AND month = ? AND day = ?`
  - 금지: 파티션 키 미지정 풀스캔, `ALLOW FILTERING`, 범위 스캔
- 단일 쿼리로 조회하는 파티션은 항상 **1개**이다 (장비 1대의 하루치)

#### 2-1-3. 요청 속도 제한 (Rate Limiting)

- fname 목록 조회 (이미지 미포함): 파티션 간 **최소 100ms 간격**
- 이미지 포함 조회: 개별 행 간 **최소 200ms 간격**
- 위 간격은 CLI 파라미터로 조정 가능하되, 기본값은 위와 같이 보수적으로 설정
- CLI 파라미터: `--read-delay-ms` (기본값 200)

#### 2-1-4. 동시 연결 제한

- Cassandra 커넥션 풀 크기를 **최대 2**로 제한한다
- 병렬 쿼리를 실행하지 않는다 — 모든 쿼리는 순차 실행
- CLI 파라미터: `--max-connections` (기본값 2)

#### 2-1-5. 실행 시간대 권장

- 프로덕션 부하가 낮은 시간대(야간/새벽)에 실행을 권장한다
- 도구 자체가 시간대를 강제하지는 않으나, 리포트에 실행 시간대를 기록하여 추적 가능하게 한다

#### 2-1-6. 로컬 캐싱을 통한 재읽기 방지

- 한 번 읽은 데이터(fname 목록, pHash 계산 결과)는 로컬 캐시(SQLite)에 저장한다
- 동일 장비·동일 날짜에 대한 재분석 시 Cassandra를 다시 읽지 않는다
- 캐시 무효화는 명시적 CLI 옵션(`--invalidate-cache`)으로만 수행

#### 2-1-7. 2단계 읽기 전략

Cassandra에서 이미지를 읽는 비용을 최소화하기 위해, 모든 분석은 2단계로 나눈다.

```
1단계: fname 목록만 조회 (image 컬럼 제외)
       → 메타데이터 파싱, 세션 분리, 클릭 클러스터링 수행
       → 이 단계에서 Cassandra 부하: 최소

2단계: 대표 프레임으로 선정된 fname에 한해 image 컬럼 조회
       → pHash 계산, 리포트용 이미지 임베딩
       → 전체 이미지의 극소수(1~5%)만 읽음
```

**예외 — 최초 실행 시 pHash 전수 계산:**
pHash 기반 분석(화면 그룹핑, 전이점 검출)을 수행하려면 모든 이미지의 pHash가 필요하다. 최초 실행 시에는 전체 이미지를 순차적으로 읽어 pHash를 계산하고 로컬 캐시에 저장한다. 이후 실행에서는 캐시에 없는 새 이미지만 증분으로 읽는다.

- 최초 실행 시 예상 소요: 3,000장 × 200ms 간격 = 약 10분/일치/장비
- 14일치 분석 시: 약 140분 (2시간 20분) — 야간 실행 권장
- 2회차 이후: 증분분만 처리, 수 분 내 완료

### 2-2. 기타 제약

| 제약 | 내용 |
|------|------|
| Cassandra 스키마 변경 불가 | 기존 테이블 구조 그대로 사용 |
| 외부 API 호출 없음 | 파일럿 단계에서 Vision AI, LLM 등 외부 서비스 미사용 |
| 단일 실행 파일 배포 | PyInstaller `--onefile`로 exe 생성, Python 미설치 환경에서 실행 가능 |
| 네트워크 환경 | Cassandra 클러스터에 직접 접근 가능한 네트워크 (VPN 또는 사내망) |
| 보안 | 스크린샷 이미지는 로컬에만 저장, 외부 전송 금지 |

---

## 3. 사용자 및 사용 시나리오

### 3-1. 대상 사용자

파일럿 단계의 사용자는 **개발자 또는 기술 엔지니어**이다. GUI가 아닌 CLI로 실행하며, 결과는 HTML 리포트로 확인한다.

### 3-2. 주요 사용 시나리오

#### 시나리오 1 — 특정 장비 분석

```
목적: 장비 EQ-2471의 2주간 조작 패턴을 분석하고 싶다
실행: snapshot-screener --eqpid EQ-2471 --from 2026-03-11 --to 2026-03-25 --db-host 10.0.1.50
결과: SnapshotScreener_EQ-2471_20260311-20260325.html 생성
행동: 리포트를 열어 대표 프레임을 검토하고, 패턴 가능성 판정을 확인
```

#### 시나리오 2 — 복수 장비 일괄 스크리닝

```
목적: 장비 50대를 대상으로 패턴 가능성이 높은 장비를 걸러내고 싶다
실행: snapshot-screener --eqpid-list eqpids.txt --from 2026-03-01 --to 2026-03-25 --db-host 10.0.1.50
결과: 장비별 개별 리포트 + 전체 요약 리포트(장비별 판정 결과 비교표) 생성
행동: 요약 리포트에서 "패턴 가능성 높음" 장비를 확인하고 Vision AI 투입 대상 선정
```

#### 시나리오 3 — 파라미터 민감도 분석

```
목적: 장비 EQ-2471의 분석 결과가 파라미터 설정에 얼마나 민감한지 확인하고 싶다
실행: snapshot-screener --eqpid EQ-2471 --from 2026-03-11 --to 2026-03-25 --db-host 10.0.1.50 --sensitivity-sweep
결과: 리포트에 레이어 C 민감도 분석 섹션이 추가됨
행동: Jaccard 유사도를 확인하여 판정 신뢰도 평가
```

---

## 4. 기능 요구사항

### 4-1. 데이터 수집 모듈

#### FR-01: fname 목록 조회

- Cassandra에서 지정된 장비·기간의 fname 목록을 조회한다
- image 컬럼을 제외하고 fname만 SELECT한다
- 쿼리 단위: 파티션 1개 = 장비 1대 × 1일
- 일별 순차 조회, 파티션 간 `--read-delay-ms` 간격 적용

#### FR-02: fname 파싱

- fname 문자열에서 클릭 좌표(x, y)와 Unix timestamp(ms)를 추출한다
- 파싱 실패 시 해당 행을 skip하고 로그에 기록한다
- fname 형식은 설정 파일에서 정규식으로 정의 가능 (아키텍처 문서와 추출기 문서 간 형식 불일치 대응)

```
# 지원할 fname 형식 (설정으로 선택)
형식 A: {x}_{y}_{timestamp}.png        (아키텍처 문서 기준)
형식 B: {timestamp}_{x}_{y}.png        (추출기 문서 기준)
형식 C: 커스텀 정규식                   (사용자 지정)
```

#### FR-03: 이미지 선택적 조회

- 대표 프레임으로 선정된 fname에 한해 image 컬럼을 조회한다
- 개별 행 단위로 조회하며, 행 간 `--read-delay-ms` 간격 적용
- Base64 → PIL Image 디코딩 후 pHash 계산 및 리포트 임베딩에 사용

#### FR-04: pHash 로컬 캐시

- SQLite 파일에 `(eqpid, fname, phash)` 매핑을 저장한다
- 캐시 히트 시 Cassandra 이미지 조회를 skip한다
- 캐시 파일 위치: `--cache-dir` 파라미터로 지정 (기본값: 실행 디렉토리)
- 캐시 무효화: `--invalidate-cache` 옵션

### 4-2. 분석 모듈

#### FR-05: 세션 분리

- 시간순 정렬된 클릭 시퀀스를 세션 단위로 분리한다
- 기본 기준: 클릭 간 gap > `--session-gap-ms` (기본값 900,000 = 15분)
- 각 세션에 고유 ID를 부여한다: `{eqpid}_S{번호:04d}`
- 각 클릭에 세션 내 순번(seq)과 이전 클릭 대비 시간차(delta_ms)를 기록한다

#### FR-06: pHash 계산 및 화면 유사도 분석

- 각 스냅샷 이미지의 pHash(perceptual hash)를 계산한다
- 인접 프레임 간 pHash distance를 계산한다
- pHash 계산에 필요한 이미지는 Cassandra에서 읽되, 캐시 우선 참조 (FR-04)

#### FR-07: 화면 그룹핑

- 인접 프레임 간 pHash distance가 `--phash-similar-threshold` (기본값 4) 이하이면 같은 화면 그룹으로 분류한다
- distance가 임계값 초과 시 새 화면 그룹을 생성한다
- 각 그룹에 고유 ID를 부여한다: `SG_{번호}`

#### FR-08: 클릭 좌표 클러스터링

- DBSCAN 알고리즘으로 클릭 좌표를 클러스터링한다
- 클릭 좌표는 0~1 비율로 정규화한 후 클러스터링한다
  - 해상도 정보: 스크린샷 이미지 크기에서 추론 (이미지를 읽는 시점에 기록)
  - 해상도를 알 수 없는 경우: `--screen-width`, `--screen-height` 파라미터로 지정 (기본값 1920×1080)
- DBSCAN 파라미터: `--dbscan-eps` (기본값 0.03, 정규화 좌표 기준), `--dbscan-min-samples` (기본값 2)

#### FR-09: 전이점 검출

다음 조건 중 하나 이상을 만족하면 전이점으로 표시한다:

- 새 화면 그룹 시작 (FR-07에서 `is_new_screen = True`)
- pHash distance > `--phash-transition-threshold` (기본값 8)
- 이전 클릭 대비 시간차 > `--delta-spike-ms` (기본값 30,000)
- 새 클릭 클러스터 시작 (FR-08에서 `is_new_click_cluster = True`)

#### FR-10: 대표 프레임 선택

파일럿 단계에서는 `simple_selector`를 기본으로 사용한다:

- 각 화면 그룹(screen_group)에서 첫 번째 프레임을 선택
- 세션 시작/종료 프레임을 추가
- 중복 제거 후 시간순 정렬

점수 기반 선택기(`scored_selector`)는 Phase 2에서 가중치 검증 후 활성화:

- 신호별 점수: session_start(+3), session_end(+3), new_screen(+4), transition_point(+3), new_click_cluster(+2)
- 상한선: 세션 내 `screen_group 수 × coverage_ratio(기본값 0.3)`, 최소 5개

선택기 전환: `--selector` 파라미터 (`simple` | `scored`, 기본값 `simple`)

### 4-3. 패턴 스크리닝 모듈 (레이어 B)

#### FR-11: 클릭 좌표 집중도 계산

```
집중도 = DBSCAN 클러스터에 속한 클릭 수 / 전체 클릭 수
(noise label = -1 제외한 클릭 비율)
```

- 판정 기준: > 70% 높음, 40~70% 중간, < 40% 낮음

#### FR-12: 세션 길이 변동계수(CV) 계산

```
CV = std(세션별 클릭 수) / mean(세션별 클릭 수)
```

- 판정 기준: < 0.3 일정, 0.3~1.0 중간, > 1.0 불일정

#### FR-13: 세션 간 화면 시퀀스 유사도 계산

- 각 세션의 화면 그룹 시퀀스(screen_group_id의 순서 리스트)를 추출한다
- 모든 세션 쌍에 대해 LCS(Longest Common Subsequence) 기반 유사도를 계산한다

```
유사도(A, B) = LCS(A, B) 길이 / max(len(A), len(B))
```

- 전체 평균 유사도를 산출한다
- 판정 기준: > 0.7 높음, 0.5~0.7 중간, < 0.5 낮음
- 구현: Python 표준 라이브러리 `difflib.SequenceMatcher` 사용

#### FR-14: 종합 판정

세 가지 신호(FR-11, FR-12, FR-13)를 종합하여 판정한다:

| 판정 | 조건 |
|------|------|
| 패턴 가능성 높음 | 3개 신호 중 2개 이상 "높음" |
| 패턴 가능성 중간 | 그 외 |
| 패턴 가능성 낮음 | 3개 신호 중 2개 이상 "낮음" |

- 판정 방향 원칙: False Negative 최소화 — 애매하면 "높음" 또는 "중간"으로 판정

### 4-4. 파라미터 민감도 분석 모듈 (레이어 C)

#### FR-15: 파라미터 sweep

- `--sensitivity-sweep` 옵션 활성화 시 실행
- `PHASH_SIMILAR_THRESHOLD`를 [3, 4, 5, 6] 범위로 변화시키며 대표 프레임 선택을 반복 수행
- 각 설정에서 선택된 대표 프레임의 fname 집합을 기록

#### FR-16: Jaccard 유사도 계산

- 인접한 threshold 설정 쌍에 대해 fname 집합 간 Jaccard 유사도를 계산한다

```
Jaccard(A, B) = |A ∩ B| / |A ∪ B|
```

- 전체 평균 Jaccard 유사도를 산출한다

#### FR-17: 민감도 판정

| 평균 Jaccard | 판정 |
|-------------|------|
| > 0.8 | 파라미터에 둔감 — 구조 명확, 높은 신뢰도 |
| 0.5 ~ 0.8 | 중간 신뢰도 |
| < 0.5 | 파라미터에 민감 — 구조 모호, 판정 보류 |

### 4-5. 리포트 생성 모듈

#### FR-18: HTML 리포트 생성

분석 완료 후 단일 HTML 파일을 자동 생성한다. 파일명 형식:

```
SnapshotScreener_{eqpid}_{from}-{to}.html
예: SnapshotScreener_EQ-2471_20260311-20260325.html
```

#### FR-19: 리포트 구성

리포트는 다음 5개 섹션으로 구성된다:

**섹션 1 — 장비 요약**
- 장비 ID, 분석 기간, 총 클릭 수, 분석 일수, 세션 수, 화면 그룹 수, 대표 프레임 수, 데이터 축소율

**섹션 2 — 대표 프레임 시퀀스**
- 세션별로 대표 프레임을 시간순 나열
- 각 프레임: 스크린샷 이미지 (Base64 인라인 임베딩) + 클릭 좌표 오버레이 (빨간 점)
- 부가 정보: fname, timestamp, 클릭 좌표, 선택 이유 태그 (세션 시작, 새 화면, 전이점, 새 클러스터), candidate_score

**섹션 3 — 패턴 스크리닝 신호 (레이어 B)**
- 클릭 좌표 집중도, 세션 길이 CV, 세션 간 시퀀스 유사도
- 각 신호별 수치 + 바 차트 + 판정 배지

**섹션 4 — 파라미터 민감도 분석 (레이어 C)**
- `--sensitivity-sweep` 활성화 시에만 표시
- threshold 쌍별 Jaccard 유사도 테이블
- 평균 Jaccard + 민감도 판정

**섹션 5 — 종합 판정**
- 모든 신호를 종합한 최종 판정 (높음/중간/낮음)
- 주의사항 및 권장 후속 조치

#### FR-20: 리포트 스타일

- 다크 테마 기반 (배경 #0f1117)
- Noto Sans KR + JetBrains Mono 폰트
- 외부 이미지/스크립트 의존 없음 — 오프라인 환경에서 열 수 있는 self-contained HTML
- 모바일 반응형 레이아웃

#### FR-21: 일괄 스크리닝 요약 리포트

복수 장비 분석 시(`--eqpid-list`) 개별 리포트 외에 요약 리포트를 추가 생성한다:

```
SnapshotScreener_Summary_{from}-{to}.html
```

내용:
- 장비별 판정 결과 비교표 (장비 ID, 클릭 집중도, CV, 시퀀스 유사도, 종합 판정)
- 판정별 장비 수 집계
- "패턴 가능성 높음" 장비 목록 하이라이트

---

## 5. 비기능 요구사항

### 5-1. 성능

| 항목 | 목표 | 비고 |
|------|------|------|
| fname 파싱 속도 | 10,000건/초 이상 | CPU 바운드, 병목 아님 |
| pHash 계산 속도 | 이미지 1장당 100ms 이내 | Pillow + imagehash |
| 전체 분석 (장비 1대 × 14일) | 3시간 이내 | Cassandra rate limiting 포함 |
| 리포트 생성 | 30초 이내 | Jinja2 렌더링 + 이미지 임베딩 |
| 메모리 사용 | 2GB 이내 | 이미지를 한 번에 메모리에 올리지 않음 |

### 5-2. 안정성

- Cassandra 연결 실패 시 자동 재시도 (최대 3회, 지수 백오프)
- 개별 파티션 조회 실패 시 해당 날짜를 skip하고 나머지 계속 진행
- 비정상 종료 시 캐시 무결성 보장 (SQLite 트랜잭션 사용)
- 진행률 로그 출력: `[12/14일] EQ-2471 2026-03-22 처리 중... (pHash 캐시 히트율: 87%)`

### 5-3. 보안

- Cassandra 인증 정보: CLI 파라미터 또는 환경변수로 전달 (하드코딩 금지)
- 로컬 캐시(SQLite)에 이미지 원본을 저장하지 않는다 — pHash 값만 저장
- 리포트 HTML에 임베딩되는 이미지는 대표 프레임(전체의 1~5%)에 한정
- 리포트 파일은 외부 전송하지 않는다 (사내 환경에서만 열람)

### 5-4. 배포

- Python 3.10+ 환경에서 개발
- PyInstaller `--onefile`로 단일 exe 생성
- 의존 라이브러리: requirements.txt에 버전 고정
- exe 파일 크기: 100MB 이내 목표

---

## 6. CLI 인터페이스

### 6-1. 필수 파라미터

| 파라미터 | 설명 | 예시 |
|----------|------|------|
| `--eqpid` | 분석 대상 장비 ID (단일) | `EQ-2471` |
| `--eqpid-list` | 분석 대상 장비 ID 목록 파일 (복수) | `eqpids.txt` |
| `--from` | 분석 시작일 (YYYY-MM-DD) | `2026-03-11` |
| `--to` | 분석 종료일 (YYYY-MM-DD) | `2026-03-25` |
| `--db-host` | Cassandra 호스트 주소 | `10.0.1.50` |

`--eqpid`와 `--eqpid-list`는 상호 배타적 (둘 중 하나 필수).

### 6-2. 선택 파라미터 — Cassandra 보호

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `--read-delay-ms` | 200 | Cassandra 쿼리 간 최소 간격 (ms) |
| `--max-connections` | 2 | Cassandra 커넥션 풀 최대 크기 |
| `--db-port` | 9042 | Cassandra 포트 |
| `--db-username` | (없음) | Cassandra 인증 사용자 |
| `--db-password` | (없음) | Cassandra 인증 비밀번호 (또는 환경변수 `SS_DB_PASSWORD`) |
| `--db-keyspace` | (필수) | Cassandra 키스페이스 |
| `--db-table` | (필수) | Cassandra 테이블명 |

### 6-3. 선택 파라미터 — 분석 설정

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `--session-gap-ms` | 900000 | 세션 분리 기준 gap (ms) |
| `--phash-similar-threshold` | 4 | 같은 화면 판정 pHash distance 임계값 |
| `--phash-transition-threshold` | 8 | 화면 전환 판정 pHash distance 임계값 |
| `--delta-spike-ms` | 30000 | 시간 급증 전이점 판정 기준 (ms) |
| `--dbscan-eps` | 0.03 | 클릭 좌표 클러스터링 eps (정규화 좌표) |
| `--dbscan-min-samples` | 2 | DBSCAN 최소 샘플 수 |
| `--screen-width` | 1920 | 화면 해상도 가로 (좌표 정규화용) |
| `--screen-height` | 1080 | 화면 해상도 세로 (좌표 정규화용) |
| `--selector` | simple | 대표 프레임 선택기 (`simple` \| `scored`) |
| `--sensitivity-sweep` | (플래그) | 레이어 C 파라미터 민감도 분석 활성화 |
| `--fname-pattern` | auto | fname 파싱 패턴 (`auto` \| `xy_ts` \| `ts_xy` \| 커스텀 정규식) |

### 6-4. 선택 파라미터 — 캐시 및 출력

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `--cache-dir` | `.` (현재 디렉토리) | pHash 캐시 SQLite 저장 위치 |
| `--output-dir` | `.` (현재 디렉토리) | HTML 리포트 출력 위치 |
| `--invalidate-cache` | (플래그) | pHash 캐시 전체 무효화 후 재계산 |
| `--verbose` | (플래그) | 상세 로그 출력 |

### 6-5. 실행 예시

```bash
# 기본 분석
snapshot-screener \
  --eqpid EQ-2471 \
  --from 2026-03-11 --to 2026-03-25 \
  --db-host 10.0.1.50 --db-keyspace factory --db-table snapshots

# 민감도 분석 포함, 보수적 rate limiting
snapshot-screener \
  --eqpid EQ-2471 \
  --from 2026-03-11 --to 2026-03-25 \
  --db-host 10.0.1.50 --db-keyspace factory --db-table snapshots \
  --sensitivity-sweep \
  --read-delay-ms 500

# 복수 장비 일괄 스크리닝
snapshot-screener \
  --eqpid-list target_equipments.txt \
  --from 2026-03-01 --to 2026-03-25 \
  --db-host 10.0.1.50 --db-keyspace factory --db-table snapshots \
  --output-dir ./reports
```

---

## 7. 데이터 모델

### 7-1. Cassandra 스키마 (기존, 변경 없음)

```
Partition Key: (eqpid, year, month, day)
Clustering Key: fname
Data: image (Base64 text)
```

### 7-2. 내부 데이터 구조

```python
@dataclass
class SnapshotMeta:
    eqpid: str
    fname: str
    timestamp_ms: int
    x: int
    y: int

@dataclass
class FrameFeature:
    # 식별
    eqpid: str
    session_id: str
    seq: int
    fname: str

    # 메타데이터 (fname에서 파싱)
    timestamp_ms: int
    x: int
    y: int
    x_norm: float          # 0~1 정규화 좌표
    y_norm: float          # 0~1 정규화 좌표
    delta_ms: Optional[int]

    # pHash (이미지에서 계산, 캐시됨)
    phash: Optional[str]
    phash_dist_prev: Optional[int]

    # 분석 결과
    screen_group_id: Optional[str]
    click_cluster_id: Optional[int]

    # 플래그
    is_session_start: bool
    is_session_end: bool
    is_new_screen: bool
    is_transition_point: bool
    is_new_click_cluster: bool

    # 후보 점수
    candidate_score: float
    candidate_flags: Optional[List[str]]
```

### 7-3. pHash 캐시 스키마 (SQLite)

```sql
CREATE TABLE phash_cache (
    eqpid     TEXT NOT NULL,
    fname     TEXT NOT NULL,
    phash     TEXT NOT NULL,
    image_w   INTEGER,           -- 이미지 가로 크기 (해상도 추론용)
    image_h   INTEGER,           -- 이미지 세로 크기
    cached_at TEXT NOT NULL,     -- ISO 8601 timestamp
    PRIMARY KEY (eqpid, fname)
);

CREATE INDEX idx_phash_cache_eqpid ON phash_cache(eqpid);
```

---

## 8. 기술 스택

| 기능 | 라이브러리 | 버전 | 비고 |
|------|-----------|------|------|
| Cassandra 조회 | `cassandra-driver` | 3.29+ | 필수, SELECT만 사용 |
| 시계열 처리 | `pandas` | 2.0+ | 세션 분리, 시퀀스 구성 |
| pHash 계산 | `Pillow`, `imagehash` | 최신 | pHash 계산 + distance 비교 |
| 클릭 클러스터링 | `scikit-learn`, `numpy` | 최신 | DBSCAN |
| 시퀀스 유사도 | `difflib` | 표준 라이브러리 | LCS 기반, 추가 설치 불필요 |
| pHash 캐시 | `sqlite3` | 표준 라이브러리 | 로컬 캐시, 추가 설치 불필요 |
| 리포트 생성 | `jinja2` | 3.0+ | HTML 템플릿 렌더링 |
| CLI | `argparse` | 표준 라이브러리 | 커맨드라인 인터페이스 |
| 분포 시각화 | `matplotlib` | 최신 | 개발/디버깅 시 pHash 분포 확인용 |
| exe 패키징 | `PyInstaller` | 6.0+ | 개발 의존성, 배포용 |

---

## 9. 처리 파이프라인

```
[입력] CLI 파라미터
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 1 — 메타데이터 수집              [Cassandra 접근] │
│                                                          │
│  1. 일별 순차 파티션 조회 (fname만, image 제외)          │
│  2. fname 파싱 → SnapshotMeta 리스트 생성              │
│  3. 파티션 간 read-delay-ms 간격 적용                   │
│                                                          │
│  Cassandra 부하: 최소 (메타데이터만)                     │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 2 — pHash 수집                   [Cassandra 접근] │
│                                                          │
│  1. 로컬 SQLite 캐시에서 기존 pHash 조회                │
│  2. 캐시 미스분만 Cassandra에서 image 조회              │
│  3. pHash 계산 → 캐시에 저장                            │
│  4. 행 간 read-delay-ms 간격 적용                       │
│                                                          │
│  Cassandra 부하: 최초 실행 시 높음 (전수), 이후 낮음    │
│  ※ 최초 실행은 야간 권장                                │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 3 — 분석                    [Cassandra 접근 없음] │
│                                                          │
│  1. 세션 분리 (FR-05)                                   │
│  2. 화면 그룹핑 (FR-07)                                 │
│  3. 클릭 좌표 클러스터링 (FR-08)                        │
│  4. 전이점 검출 (FR-09)                                 │
│  5. 대표 프레임 선택 (FR-10)                            │
│  6. 패턴 스크리닝 신호 계산 (FR-11~14)                  │
│  7. 파라미터 민감도 분석 (FR-15~17, 옵션)               │
│                                                          │
│  Cassandra 부하: 없음 (로컬 데이터만 사용)              │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 4 — 리포트 이미지 수집           [Cassandra 접근] │
│                                                          │
│  1. 대표 프레임 fname 목록 확정 (Phase 3 결과)          │
│  2. 해당 fname의 image만 Cassandra에서 조회             │
│  3. 행 간 read-delay-ms 간격 적용                       │
│                                                          │
│  Cassandra 부하: 극소 (전체의 1~5%만 읽기)              │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 5 — 리포트 생성             [Cassandra 접근 없음] │
│                                                          │
│  1. 이미지에 클릭 좌표 오버레이                         │
│  2. Jinja2 템플릿 렌더링                                │
│  3. HTML 파일 출력                                      │
│                                                          │
│  Cassandra 부하: 없음                                    │
└─────────────────────────────────────────────────────────┘
```

---

## 10. Cassandra 보호 매커니즘 요약

전체 파이프라인에서 Cassandra에 접근하는 구간과 보호 수단을 정리한다.

| Phase | Cassandra 접근 | 읽는 데이터 | 보호 수단 |
|-------|---------------|-------------|-----------|
| Phase 1 | O | fname만 (image 제외) | 포인트 쿼리, rate limiting |
| Phase 2 | O (캐시 미스 시) | image (pHash 계산용) | 캐시 우선, rate limiting, 순차 처리 |
| Phase 3 | X | — | 로컬 데이터만 사용 |
| Phase 4 | O | image (대표 프레임만) | 전체의 1~5%, rate limiting |
| Phase 5 | X | — | 로컬 데이터만 사용 |

**최악 시나리오 Cassandra 부하 추정 (장비 1대 × 14일, 최초 실행):**

```
Phase 1: 14 파티션 × fname 목록 조회 = 14 쿼리
Phase 2: 3,000장/일 × 14일 = 42,000 이미지 읽기 (캐시 없는 최초 실행)
         42,000 × 200ms 간격 = 약 140분
Phase 4: 대표 프레임 ~23장 = 23 쿼리 (무시할 수준)

총 Cassandra 읽기 쿼리: ~42,037건
총 소요 시간: ~140분 (Phase 2가 지배적)
초당 쿼리 수: ~5 QPS (rate limiting에 의해 제한됨)
```

**2회차 이후 (캐시 히트):**

```
Phase 1: 14 쿼리 (동일)
Phase 2: 신규 이미지만 (예: 1일치 3,000장) = 10분
Phase 4: ~23 쿼리 (동일)

총 소요 시간: ~10분
```

---

## 11. 파일럿 범위 및 성공 기준

### 11-1. 파일럿 범위

| 항목 | 범위 |
|------|------|
| 대상 장비 | 3~5대 |
| 분석 기간 | 2~4주 |
| UI 타입 | 제한 없음 (Vision AI 미사용) |
| 실행 환경 | 개인 PC 또는 SSH 경유 서버 |

### 11-2. 성공 기준

| 기준 | 목표 | 측정 방법 |
|------|------|-----------|
| 데이터 축소율 | ≥ 70% | 대표 프레임 수 / 전체 클릭 수 |
| 업무 흐름 이해 가능성 | 대표 프레임만으로 이해 가능 | 사람의 육안 검토 (주관적 판단) |
| Cassandra 영향 | 프로덕션 지표 변화 없음 | Cassandra 모니터링 대시보드 확인 |
| 스크리너 recall | ≥ 95% | ground truth 대비 (수동 레이블링 10대) |
| 레이어 C 변별력 | bimodal 분포 확인 | Jaccard 유사도 분포 히스토그램 |

### 11-3. 파일럿 검증 체크리스트

#### 시작 전

- [ ] fname 형식 확정 (아키텍처 문서 vs 추출기 문서 불일치 해소)
- [ ] Cassandra 네트워크 접근 확인 (IP/포트/인증)
- [ ] 파일럿 대상 장비 3~5대 선정

#### 1~2주차

- [ ] SnapshotScreener 코어 구현 완료 (Phase 1~5)
- [ ] 장비 1대 × 1일치 최초 실행 → pHash 캐시 구축 확인
- [ ] pHash distance 분포 측정 → 임계값 1차 설정
- [ ] Cassandra 모니터링: 실행 중 read latency 변화 없음 확인
- [ ] simple_selector 대표 프레임 추출 → 육안 검토

#### 3~4주차

- [ ] 레이어 C 민감도 sweep 실행 → bimodal 여부 확인
- [ ] ground truth 레이블 세트 구축 (최소 10대)
- [ ] recall 측정 (목표 ≥ 95%)
- [ ] 일괄 스크리닝 (장비 5대) 실행 → 요약 리포트 확인

#### 종료 판정

- [ ] 핵심 질문: "대표 프레임만으로 업무 흐름을 이해할 수 있는가?"
- [ ] Cassandra 무영향 확인 (전 기간)
- [ ] Phase 2 확장 여부 결정

---

## 12. 향후 확장 (Phase 2, 본 PRD 범위 밖)

파일럿 성공 시 고려할 확장 사항을 기록한다. 본 PRD의 구현 범위에는 포함되지 않는다.

- pHash 컬럼을 Cassandra 스키마에 추가하여 이미지 전수 읽기 제거
- 세션 분리 복합 기준 (시간 gap + pHash 상태 변화)
- 점수 기반 선택기 가중치 학습 (ablation + Vision AI 인식률 상관 분석)
- 생산 캘린더 연동 (품목 전환 시점 기반 세션 분리)
- 웹 UI (Flask/FastAPI) — 비기술 사용자 대응
- 대규모 배치 스케줄링 (Airflow 등)
- Kafka 기반 실시간 증분 분석

---

## 13. 용어 정의

| 용어 | 정의 |
|------|------|
| fname | 스크린샷 파일명. 클릭 좌표와 timestamp가 인코딩되어 있음 |
| pHash | Perceptual Hash. 이미지의 시각적 유사도를 비교하기 위한 해시값 |
| 세션 | 연속된 UI 조작의 단위. 일정 시간 이상 gap이 발생하면 분리 |
| 화면 그룹 | pHash 유사도 기준으로 같은 화면으로 분류된 프레임 집합 |
| 전이점 | 화면 전환, 시간 급증, 클릭 위치 변화 등 조작 흐름의 변곡점 |
| 대표 프레임 | 전체 스냅샷에서 업무 흐름을 대표하도록 선별된 프레임 |
| 레이어 A | Vision AI 입력 축소 기능 |
| 레이어 B | 패턴 가능성 사전 스크리닝 기능 |
| 레이어 C | 파라미터 민감도 기반 신뢰도 판정 기능 |
| rate limiting | Cassandra 쿼리 간 의도적 지연을 두어 부하를 제한하는 메커니즘 |

---

*이 PRD는 파일럿 단계의 개발 범위를 정의한다. 파일럿 결과에 따라 Phase 2 PRD를 별도 작성한다.*
