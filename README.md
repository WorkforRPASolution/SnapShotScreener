# SnapshotScreener

공장 장비 UI 조작 스크린샷에서 대표 프레임을 자동 추출하고, 자동화 가능한 반복 패턴의 존재 가능성을 사전 판정하는 CLI 도구.

---

## 목차

1. [제품 개요](#1-제품-개요)
2. [주요 기능](#2-주요-기능)
3. [설치](#3-설치)
4. [빠른 시작](#4-빠른-시작)
5. [CLI 레퍼런스](#5-cli-레퍼런스)
6. [분석 파이프라인 상세](#6-분석-파이프라인-상세)
7. [리포트 해석 가이드](#7-리포트-해석-가이드)
8. [Cassandra 보호 메커니즘](#8-cassandra-보호-메커니즘)
9. [파라미터 튜닝 가이드](#9-파라미터-튜닝-가이드)
10. [다국어 지원](#10-다국어-지원)
11. [기술 스택](#11-기술-스택)
12. [프로젝트 구조](#12-프로젝트-구조)
13. [용어집](#13-용어집)

---

## 1. 제품 개요

### 한 줄 정의

공장 장비 UI 조작 스크린샷에서 **대표 프레임을 자동 추출**하고, **자동화 가능한 반복 패턴의 존재 가능성을 사전 판정**하는 CLI 도구.

### 어떤 문제를 해결하는가

공장 장비 UI 자동화 프로젝트에서 수집되는 스크린샷은 하루 약 3,000장/장비 x 1만 대 이상 = 수천만 장 규모이다. 이 전체를 Vision AI에 투입하는 것은 비용과 시간 모두 비현실적이다. SnapshotScreener는 Vision AI 투입 전 단계에서 두 가지 필터링을 수행한다:

1. **대표 프레임 추출** -- 한 장비의 수천 장 스냅샷에서 업무 흐름을 대표하는 수십 장만 선별 (70% 이상 데이터 축소)
2. **패턴 가능성 사전 판정** -- 1만 대 장비 중 자동화 패턴이 존재할 가능성이 높은 장비만 선별하여 Vision AI 투입 대상 축소

### 시스템 아키텍처 내 위치

```
Layer 1 -- 엣지 (장비 PC Agent)           [완성]
Layer 2 -- 중앙 수집 (CassandraDB)        [완성]
Layer 3 -- AI 분석 파이프라인              [미완성]
  +-- Step 0: SnapshotScreener  <<< 이 도구
  +-- Step 1: fname 파싱 + 조작 시퀀스 재구성
  +-- Step 2: Vision AI UI 요소 인식
  +-- Step 3: 반복 패턴 탐지
  +-- Step 4: 자동화 시나리오 생성
Layer 4 -- 관리 포털                       [미완성]
```

SnapshotScreener는 Layer 3의 **Step 0 -- 전처리 필터**로서, 이후 Step들의 입력 범위를 좁히는 역할을 한다. Step 1~4와 독립적으로 먼저 개발 및 검증이 가능하다.

### 이 도구가 아닌 것

- **Vision AI가 아니다** -- 이미지의 UI 요소를 인식하지 않는다
- **자동화 시나리오를 생성하지 않는다** -- 패턴의 존재 가능성만 판정한다
- **"패턴 있음" 판정이 "자동화 가능" 확정은 아니다** -- 최종 판단은 사람이 한다
- **실시간 스트리밍 도구가 아니다** -- 배치 분석 도구이다

---

## 2. 주요 기능

### 대표 프레임 추출 (Layer A)

대량 스냅샷에서 업무 흐름을 대표하는 프레임만 추출하여 Vision AI 처리량을 줄인다. pHash 기반 화면 그룹핑, DBSCAN 클릭 좌표 클러스터링, 세션 분리를 활용하여 대표 프레임을 선별한다.

### 패턴 가능성 사전 스크리닝 (Layer B)

fname 메타데이터와 pHash만으로 "이 장비에 자동화 가능한 반복 패턴이 존재할 가능성"을 사전 판정한다. 세션 길이 변동계수(CV)와 세션 간 화면 시퀀스 유사도(LCS)를 종합하여 판정한다. 클릭 좌표 집중도는 고정 UI 장비에서 변별력이 없어 참고용으로만 표시한다.

### 파라미터 민감도 분석 (Layer C)

핵심 파라미터(pHash 임계값)를 범위 내에서 sweep하면서 결과의 안정성 자체를 메타 신호로 활용한다. 파라미터를 바꿔도 결과가 안 흔들리는 장비는 구조가 명확하므로, 분석 신뢰도 등급을 부여할 수 있다.

### 트리아지 모드 — 대규모 Fleet 경량 스크리닝

1만 대 이상의 장비를 이미지 읽기 없이 빠르게 스캔하여 자동화 패턴 가능성이 높은 장비를 선별한다. `snapshotlist` 테이블(월별 파티션, image 없음)을 사용하여 fname 메타데이터만으로 세션 길이 CV를 계산하고 판정한다. 클릭 좌표 집중도는 참고용으로 표시한다. 10,000대 기준 20~45분 소요.

### HTML 리포트 자동 생성

분석 완료 후 self-contained HTML 리포트를 자동 생성한다. 대표 프레임 이미지, 클릭 좌표 오버레이, 스크리닝 신호, 민감도 분석 결과를 포함하며, 오프라인 환경에서 열 수 있다.

---

## 3. 설치

### 요구 환경

- **Python 3.10 이상**
- Cassandra 클러스터에 네트워크 접근 가능한 환경 (VPN 또는 사내망)

### 지원 OS

| OS | 최소 버전 | 비고 |
|----|-----------|------|
| **Windows** | Windows 8.1 / Server 2012 R2 | Python 3.10+ 런타임 요구. **Server 2012 (non-R2) 미지원** |
| **Linux** | glibc 2.17+ (CentOS 7, Ubuntu 14.04+) | 대부분의 현대 배포판 지원 |
| **macOS** | 10.9 (Mavericks)+ | Apple Silicon (M1+) 및 Intel 모두 지원 |

> **PyInstaller exe도 동일한 OS 제약이 적용된다.** exe에 Python 런타임이 내장되므로 대상 PC에 Python 설치는 불필요하지만, 내장된 런타임이 OS API를 요구하므로 위 최소 버전 미만에서는 실행되지 않는다.

### pip 설치

```bash
# 저장소 클론
git clone <repository-url>
cd SnapshotScreener

# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 패키지 설치
pip install -e .
```

### PyInstaller exe 빌드

Python이 설치되지 않은 환경에서 실행해야 하는 경우, 단일 exe 파일로 빌드할 수 있다.

```bash
# 런타임 + 개발 의존성 모두 설치
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 단일 exe 빌드 (설정은 snapshot_screener.spec에 정의됨)
pyinstaller snapshot_screener.spec
```

빌드된 파일은 `dist/snapshot-screener` (또는 `dist/snapshot-screener.exe`)에 생성된다. 빌드 시간은 수 분 소요될 수 있다 (Python 런타임 + 전체 라이브러리를 단일 파일로 번들링).

> **참고**: `pip install -e .`로 설치한 경우 `requirements.txt` 설치를 생략할 수 있다. 빌드 설정(hidden imports, excludes 등)은 `snapshot_screener.spec` 파일에서 관리한다.

### 의존 라이브러리

| 라이브러리 | 용도 |
|-----------|------|
| `cassandra-driver` (>=3.29) | Cassandra 조회 (SELECT만 사용) |
| `Pillow` | 이미지 디코딩 |
| `imagehash` | pHash 계산 및 distance 비교 |
| `scikit-learn` | DBSCAN 클릭 좌표 클러스터링 |
| `numpy` | 수치 연산 |
| `jinja2` | HTML 리포트 템플릿 렌더링 |
| `matplotlib` | 개발/디버깅 시 분포 시각화 |

---

## 4. 빠른 시작

### Config 파일로 실행 (권장)

모든 파라미터를 YAML config 파일에 정의하여 간편하게 실행할 수 있다. 예제 config는 `config/example.yaml`을 참고한다.

```bash
# config 파일만으로 실행
snapshot-screener --config config/my_config.yaml

# config 파일 + CLI 인자 오버라이드 (CLI 인자가 우선)
snapshot-screener --config config/my_config.yaml --verbose --eqpid EQ-9999
```

**config 파일 예시** (`config/my_config.yaml`):

```yaml
# 분석 대상
eqpid: EQ-2471
date_from: "2026-03-11"
date_to: "2026-03-25"

# Cassandra 접속
db_host: 10.0.1.50
db_port: 9042
db_keyspace: factory
db_table: snapshots
db_username: null            # 인증 불필요 시 null
db_password: null            # 또는 SS_DB_PASSWORD 환경변수 사용 권장

# Cassandra 보호 (PRD 기본값)
read_delay_ms: 200
fname_delay_ms: 100
max_connections: 2

# 분석 파라미터
session_gap_ms: 900000
phash_similar_threshold: 4
phash_transition_threshold: 8
selector: simple
sensitivity_sweep: false
fname_pattern: auto

# 출력
cache_dir: "."
output_dir: "./output"
verbose: false
lang: ko                 # ko (한국어) | en (English)
```

config 파일에서 지원하는 모든 키는 CLI 파라미터와 1:1 대응한다. 전체 파라미터 목록은 [5. CLI 레퍼런스](#5-cli-레퍼런스)를 참조한다. CLI 인자를 추가하면 config 파일의 값을 오버라이드한다.

### 기본 실행 (단일 장비, CLI 직접 지정)

```bash
snapshot-screener \
  --eqpid EQ-2471 \
  --from 2026-03-11 --to 2026-03-25 \
  --db-host 10.0.1.50 --db-keyspace factory --db-table snapshots
```

결과: `SnapshotScreener_EQ-2471_20260311-20260325.html` 생성

### 복수 장비 일괄 스크리닝

장비 ID를 한 줄에 하나씩 기록한 텍스트 파일을 준비한다:

```
# eqpids.txt
EQ-2471
EQ-2472
EQ-3100
EQ-3101
EQ-3102
```

```bash
snapshot-screener \
  --eqpid-list eqpids.txt \
  --from 2026-03-01 --to 2026-03-25 \
  --db-host 10.0.1.50 --db-keyspace factory --db-table snapshots \
  --output-dir ./reports
```

결과: 장비별 개별 리포트 + `SnapshotScreener_Summary_20260301-20260325.html` 요약 리포트 생성

### 민감도 분석 포함 실행

```bash
snapshot-screener \
  --eqpid EQ-2471 \
  --from 2026-03-11 --to 2026-03-25 \
  --db-host 10.0.1.50 --db-keyspace factory --db-table snapshots \
  --sensitivity-sweep \
  --read-delay-ms 500
```

결과: 리포트에 Layer C 파라미터 민감도 분석 섹션이 추가된다.

### 트리아지 모드 (대규모 Fleet 스크리닝)

1만 대 이상의 장비를 이미지 읽기 없이 빠르게 스캔한다. 장비 계층(process/model) CSV 파일이 필요하다.

**장비 CSV 형식** (열 순서 기반, 헤더명 무관):

```csv
process,model,eqpid
PROCESS_A,MODEL_X,EQ-2471
PROCESS_A,MODEL_X,EQ-2472
PROCESS_B,MODEL_Y,EQ-3100
```

**Config 파일로 실행 (권장):**

기존 config 파일에 `triage: true`와 `csv` 키만 추가하면 DB/날짜 설정을 공유할 수 있다. `--triage` 플래그 없이 config만으로 트리아지가 활성화된다.

```yaml
# config/triage.yaml
triage: true
csv: equipment.csv           # 상대 경로(config 기준) 또는 절대 경로

date_from: "2026-03-15"
date_to: "2026-03-29"
db_host: 10.0.1.50
db_keyspace: ars
output_dir: ./triage_output
```

```bash
snapshot-screener --config config/triage.yaml
```

> **CSV 경로 해석 규칙**: 절대 경로는 그대로 사용된다. 상대 경로는 config 파일이 있으면 config 파일 디렉터리 기준, 없으면 현재 작업 디렉터리(CWD) 기준으로 해석된다.

**CLI 직접 지정:**

```bash
# 트리아지 실행
snapshot-screener --triage \
  --csv equipment.csv \
  --from 2026-03-15 --to 2026-03-29 \
  --db-host 10.0.1.50 --db-keyspace ars \
  --output-dir ./triage_output

# 날짜 생략 시 최근 14일 자동 설정
snapshot-screener --triage \
  --csv equipment.csv \
  --db-host 10.0.1.50 --db-keyspace ars
```

결과: `TriageReport_*.csv` + `TriageReport_*.json` + `TriageReport_*.html` 생성

**안전장치:**
- 톰스톤 회피 쿼리 (`fname >= ?`)로 TTL 만료 행 스캔 방지
- 회로 차단기: Cassandra 연속 실패 시 자동 중단 + 부분 결과 저장
- JSONL 저널: 장비별 결과 즉시 기록, Ctrl+C에도 부분 결과 보존

### 출력 파일 확인

```bash
# 개별 장비 리포트
ls SnapshotScreener_EQ-2471_*.html

# 일괄 스크리닝 요약 리포트
ls SnapshotScreener_Summary_*.html

# 트리아지 리포트
ls TriageReport_*.html TriageReport_*.csv TriageReport_*.json

# pHash 캐시 (SQLite)
ls phash_cache.db
```

---

## 5. CLI 레퍼런스

### Config 파일

| 파라미터 | 설명 | 예시 |
|----------|------|------|
| `--config` | YAML config 파일 경로 | `config/my_config.yaml` |

config 파일을 지정하면 파일에 정의된 값이 기본값으로 적용된다. CLI 인자를 추가로 지정하면 config 파일의 값을 오버라이드한다. 전체 config 파일 예시는 `config/example.yaml`을 참고한다.

### 필수 파라미터

| 파라미터 | Config 키 | 설명 | 예시 |
|----------|-----------|------|------|
| `--eqpid` | `eqpid` | 분석 대상 장비 ID (단일) | `EQ-2471` |
| `--eqpid-list` | `eqpid_list` | 분석 대상 장비 ID 목록 파일 (복수) | `eqpids.txt` |
| (config 전용) | `eqpids` | 복수 장비 ID 리스트 (YAML) | `[EQ-2471, EQ-2472]` |
| `--from` | `date_from` | 분석 시작일 (YYYY-MM-DD) | `2026-03-11` |
| `--to` | `date_to` | 분석 종료일 (YYYY-MM-DD) | `2026-03-25` |
| `--db-host` | `db_host` | Cassandra 호스트 주소 | `10.0.1.50` |
| `--db-keyspace` | `db_keyspace` | Cassandra 키스페이스 | `factory` |
| `--db-table` | `db_table` | Cassandra 테이블 이름 (기본: `snapshot`) | `snapshots` |

`--eqpid`와 `--eqpid-list`는 상호 배타적이다. 둘 중 하나를 반드시 지정해야 한다. config 파일에서는 `eqpids` 키로 복수 장비를 직접 리스트로 지정할 수도 있다.

### 선택 파라미터 -- Cassandra 보호

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `--db-port` | 9042 | Cassandra 포트 |
| `--db-username` | (없음) | Cassandra 인증 사용자 |
| `--db-password` | (없음) | Cassandra 인증 비밀번호 (환경변수 `SS_DB_PASSWORD` 권장) |
| `--read-delay-ms` | 200 | 이미지 읽기 간격 (ms) |
| `--fname-delay-ms` | 100 | 파일명 쿼리 간격 (ms) |
| `--max-connections` | 2 | 최대 Cassandra 연결 수 |

### 선택 파라미터 -- 분석 설정

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `--session-gap-ms` | 900000 | 세션 분리 기준 gap (ms, 15분) |
| `--phash-similar-threshold` | 4 | 같은 화면 판정 pHash distance 임계값 |
| `--phash-transition-threshold` | 8 | 화면 전환 판정 pHash distance 임계값 |
| `--delta-spike-ms` | 30000 | 시간 급증 전이점 판정 기준 (ms) |
| `--dbscan-eps` | 0.03 | DBSCAN epsilon (정규화 좌표 기준) |
| `--dbscan-min-samples` | 2 | DBSCAN 최소 샘플 수 |
| `--screen-width` | 1920 | 화면 해상도 가로 (좌표 정규화용, px) |
| `--screen-height` | 1080 | 화면 해상도 세로 (좌표 정규화용, px) |
| `--selector` | simple | 대표 프레임 선택기 (`simple` 또는 `scored`) |
| `--sensitivity-sweep` | (플래그) | Layer C 파라미터 민감도 분석 활성화 |
| `--fname-pattern` | auto | fname 파싱 패턴 (`auto` 또는 커스텀 정규식) |

### 선택 파라미터 -- 캐시/출력

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `--cache-dir` | `.` (현재 디렉토리) | pHash 캐시 SQLite 저장 위치 |
| `--output-dir` | `.` (현재 디렉토리) | HTML 리포트 출력 위치 |
| `--invalidate-cache` | (플래그) | pHash 캐시 전체 무효화 후 재계산 |
| `--verbose` | (플래그) | 디버그 로깅 활성화 |
| `--lang` | ko | 출력 언어 (`ko` 한국어, `en` English). 콘솔 로그, HTML 리포트, 에러 메시지에 적용 |

### 트리아지 모드 파라미터

| 파라미터 | Config 키 | 기본값 | 설명 |
|----------|-----------|--------|------|
| `--triage` | `triage` | (플래그) | 트리아지 모드 활성화. Config 파일에서 `triage: true`로도 활성화 가능 |
| `--csv` | `csv` | (필수) | 장비 계층 CSV 파일 경로 (열 순서: process, model, eqpid). 절대/상대 경로 모두 가능 |
| `--db-snapshotlist-table` | `db_snapshotlist_table` | `snapshotlist` | snapshotlist 테이블명 |

트리아지 모드에서는 `--eqpid`, `--eqpid-list`, `--db-table`, `--phash-*`, `--selector`, `--sensitivity-sweep`, `--cache-dir`, `--invalidate-cache` 인자가 무시된다. `--from`/`--to` 미지정 시 최근 14일이 자동 설정된다. `--db-host`, `--db-keyspace`, `--db-port` 등 Cassandra 접속 설정은 일반 모드와 공유한다.

**snapshotlist 테이블 요구 스키마:**

```
Partition Key: (eqpid, year, month)
Clustering Key: fname (ASC)
```

`fname` 컬럼만 사용하며, image 데이터는 불필요하다. 테이블의 TTL이 15일이므로 최근 데이터만 조회 가능하다.

### 환경변수

| 변수 | 설명 |
|------|------|
| `SS_DB_PASSWORD` | Cassandra 인증 비밀번호. `--db-password`보다 이 환경변수 사용을 권장한다. CLI 인수로 비밀번호를 전달하면 보안 경고가 출력된다. |

```bash
# 환경변수로 비밀번호 설정
export SS_DB_PASSWORD="your_password"
snapshot-screener --eqpid EQ-2471 --from 2026-03-11 --to 2026-03-25 \
  --db-host 10.0.1.50 --db-keyspace factory --db-table snapshots \
  --db-username admin
```

### Exit 코드

| 코드 | 의미 |
|------|------|
| 0 | 정상 완료 |
| 1 | 사용자 입력 오류 (잘못된 파라미터, 날짜 형식 등) |
| 2 | 분석 오류 (처리 중 예외 발생) |
| 3 | Cassandra 연결 실패 |
| 130 | 사용자에 의한 중단 (Ctrl+C) |

---

## 6. 분석 파이프라인 상세

### 5-Phase 파이프라인

```
[입력] CLI 파라미터
    |
    v
+-----------------------------------------------------------+
|  Phase 1 -- 메타데이터 수집              [Cassandra 접근]  |
|                                                            |
|  1. 일별 순차 파티션 조회 (fname만, image 제외)            |
|  2. fname 파싱 -> SnapshotMeta 리스트 생성                 |
|  3. 파티션 간 fname-delay-ms 간격 적용                     |
|                                                            |
|  Cassandra 부하: 최소 (메타데이터만)                       |
+-----------------------------+-----------------------------+
                              |
                              v
+-----------------------------------------------------------+
|  Phase 2 -- pHash 수집                   [Cassandra 접근]  |
|                                                            |
|  1. 로컬 SQLite 캐시에서 기존 pHash 조회                  |
|  2. 캐시 미스분만 Cassandra에서 image 조회                 |
|  3. pHash 계산 -> 캐시에 저장                              |
|  4. 행 간 read-delay-ms 간격 적용                          |
|                                                            |
|  Cassandra 부하: 최초 실행 시 높음, 이후 낮음              |
+-----------------------------+-----------------------------+
                              |
                              v
+-----------------------------------------------------------+
|  Phase 3 -- 분석                    [Cassandra 접근 없음]  |
|                                                            |
|  1. 세션 분리                                              |
|  2. 화면 그룹핑 (pHash 기반)                               |
|  3. 클릭 좌표 클러스터링 (DBSCAN)                          |
|  4. 전이점 검출                                            |
|  5. 대표 프레임 선택                                       |
|  6. 패턴 스크리닝 신호 계산 (Layer B)                      |
|  7. 파라미터 민감도 분석 (Layer C, 옵션)                   |
|                                                            |
|  Cassandra 부하: 없음 (로컬 데이터만 사용)                 |
+-----------------------------+-----------------------------+
                              |
                              v
+-----------------------------------------------------------+
|  Phase 4 -- 리포트 이미지 수집           [Cassandra 접근]  |
|                                                            |
|  1. 대표 프레임 fname 목록 확정 (Phase 3 결과)             |
|  2. 해당 fname의 image만 Cassandra에서 조회                |
|  3. 행 간 read-delay-ms 간격 적용                          |
|                                                            |
|  Cassandra 부하: 극소 (전체의 1~5%만 읽기)                 |
+-----------------------------+-----------------------------+
                              |
                              v
+-----------------------------------------------------------+
|  Phase 5 -- 리포트 생성             [Cassandra 접근 없음]  |
|                                                            |
|  1. 이미지에 클릭 좌표 오버레이                            |
|  2. Jinja2 템플릿 렌더링                                   |
|  3. HTML 파일 출력                                         |
|                                                            |
|  Cassandra 부하: 없음                                      |
+-----------------------------------------------------------+
```

### Phase 1: 메타데이터 수집

Cassandra에서 지정된 장비와 기간의 fname 목록을 조회한다. image 컬럼은 제외하여 Cassandra 부하를 최소화한다. 일별 순차 조회(파티션 1개 = 장비 1대 x 1일)로 처리하며, 파티션 간 `--fname-delay-ms`(기본 100ms) 간격을 적용한다.

fname 문자열에서 클릭 좌표(x, y)와 Unix timestamp(ms)를 파싱한다. 프로덕션 파일명 형식은 `{timestamp}_[{x}][{y}].png`이다 (예: `1774568805575_[1338][403].png`).

`--fname-pattern` 파라미터로 파싱 패턴을 지정할 수 있다:
- `auto` (기본값): 프로덕션 형식 `{timestamp}_[{x}][{y}].png` 사용
- 커스텀 정규식: `(?P<x>\d+)`, `(?P<y>\d+)`, `(?P<ts>\d+)` named group 포함 정규식

**비클릭 스냅샷 필터링**: x 또는 y 좌표가 9999 이상인 스냅샷은 마우스 클릭이 아닌 자동 캡처로 간주하여 분석에서 제외한다.

### Phase 2: pHash 수집 (캐시 우선)

각 스냅샷 이미지의 pHash(perceptual hash)를 계산한다. 로컬 SQLite 캐시를 우선 참조하여 Cassandra 이미지 조회를 최소화한다.

- 캐시 히트: Cassandra 조회 없이 캐시에서 pHash 값을 가져온다
- 캐시 미스: Cassandra에서 image를 조회하여 pHash를 계산하고 캐시에 저장한다
- 행 간 `--read-delay-ms`(기본 200ms) 간격을 적용한다

### Phase 3: 분석

Cassandra 접근 없이 로컬 데이터만으로 수행하는 핵심 분석 단계이다.

1. **세션 분리**: 클릭 간 gap이 `--session-gap-ms`(기본 15분) 초과 시 새 세션으로 분리. 세션 ID 형식: `{eqpid}_S{번호:04d}`
2. **화면 그룹핑**: 인접 프레임 간 pHash distance가 `--phash-similar-threshold`(기본 4) 이하이면 같은 화면 그룹으로 분류
3. **클릭 좌표 클러스터링**: 좌표를 0~1로 정규화한 후 DBSCAN으로 클러스터링
4. **전이점 검출**: 새 화면, pHash distance 급증, 시간 급증, 새 클릭 클러스터 중 하나 이상이면 전이점으로 표시
5. **대표 프레임 선택**: 각 화면 그룹의 첫 프레임 + 세션 시작/종료 프레임을 선택
6. **스크리닝 신호 계산**: 클릭 집중도, 세션 CV, 시퀀스 유사도를 산출하고 종합 판정
7. **민감도 분석** (옵션): `--sensitivity-sweep` 활성화 시, pHash 임계값 [3, 4, 5, 6]으로 sweep하여 Jaccard 유사도 계산

### Phase 4: 리포트 이미지 수집

대표 프레임으로 선정된 fname에 한해 Cassandra에서 image를 조회한다. 전체 이미지의 극소수(1~5%)만 읽으므로 Cassandra 부하가 매우 낮다.

### Phase 5: HTML 리포트 생성

대표 프레임 이미지에 클릭 좌표를 오버레이하고, Jinja2 템플릿으로 HTML 리포트를 렌더링한다. 외부 이미지/스크립트 의존 없이 self-contained HTML 파일로 생성된다.

---

## 7. 리포트 해석 가이드

> 이 섹션은 SnapshotScreener가 생성한 HTML 리포트를 해석하는 방법을 상세히 설명한다.

### 섹션 1 -- 장비 요약

리포트 상단에 표시되는 장비 요약 카드의 각 항목 의미:

| 항목 | 의미 |
|------|------|
| 총 클릭 수 | 분석 기간 내 기록된 전체 스냅샷(클릭 이벤트) 수 |
| 분석 일수 | `--from`부터 `--to`까지의 일수 |
| 세션 수 | 시간 gap 기준으로 분리된 연속 작업 단위의 수 |
| 화면 그룹 | pHash 유사도 기준으로 같은 화면으로 분류된 그룹의 수 |
| 대표 프레임 | 전체 스냅샷에서 선별된 대표 프레임의 수 |
| 데이터 축소율 | `1 - (대표 프레임 수 / 전체 클릭 수)`. 값이 높을수록 많은 데이터를 축소했다는 의미 |

### 섹션 2 -- 대표 프레임 시퀀스

세션별로 대표 프레임이 시간순으로 나열된다.

**프레임 카드 읽는 법:**
- 각 카드에는 스크린샷 이미지가 표시되며, 클릭 좌표 위치에 빨간 점이 오버레이된다
- 빨간 점은 해당 클릭이 실제로 발생한 화면 좌표를 나타낸다
- fname, timestamp, 클릭 좌표가 부가 정보로 표시된다

**태그의 의미:**

| 태그 | 의미 |
|------|------|
| 세션 시작 (`session_start`) | 해당 세션의 첫 번째 클릭. 새로운 작업 단위의 시작점 |
| 새 화면 (`new_screen`) | pHash가 이전 프레임과 크게 달라져 새 화면 그룹이 시작된 프레임 |
| 전이점 (`transition_point`) | 화면 전환, 시간 급증, 클릭 위치 변화 등 조작 흐름의 변곡점 |
| 새 클러스터 (`new_click_cluster`) | 클릭 좌표가 이전과 다른 클러스터 영역으로 이동한 프레임 |

**candidate_score:**
- 각 프레임에 부여된 대표성 점수. 여러 태그가 중복될수록 높아진다
- 점수 자체의 절대값보다 상대적 비교가 의미 있다

### 섹션 3 -- 패턴 스크리닝 신호 (Layer B)

세션 길이 CV와 화면 시퀀스 유사도를 기반으로 자동화 가능한 반복 패턴의 존재 가능성을 판정한다. 클릭 좌표 집중도는 고정 UI 장비에서 대부분 0.99 이상으로 나타나 변별력이 없으므로 참고용으로만 표시하고 판정에는 사용하지 않는다.

#### 클릭 좌표 집중도 (참고용 — 판정 미사용)

- **계산법**: DBSCAN 클러스터에 속한 클릭 수 / 전체 클릭 수 (noise label = -1 제외)
- **의미**: 작업자가 매번 같은 위치를 클릭하는가
- **판정에서 제외된 사유**: 공장 장비는 고정 UI 레이아웃이 대부분이라, 수동 조작이든 자동화든 항상 같은 버튼 위치를 클릭한다. 따라서 거의 모든 장비에서 집중도가 0.99 이상으로 나타나며, 자동화 여부를 구분하는 변별력이 없다.

#### 세션 길이 변동계수 (CV)

- **계산법**: `std(세션별 클릭 수) / mean(세션별 클릭 수)` (클릭 3회 이상인 세션만 포함)
- **의미**: 매 세션의 작업량이 일정한가
- **판정 기준**:

| 범위 | 판정 | 해석 |
|------|------|------|
| < 0.3 | 높음 (일정) | 같은 업무를 반복하고 있을 가능성이 높다. 세션마다 비슷한 수의 클릭이 발생한다 |
| 0.3 ~ 1.0 | 중간 | 대체로 비슷하나 일부 세션에서 편차가 있다 |
| > 1.0 | 낮음 (불일정) | 업무 종류가 세션마다 다르다. 작업량의 편차가 크다 |

> **참고**: 트리아지 모드에서는 CV 임계값이 다르다 (< 0.25 = 높음, 0.25 ~ 0.6 = 중간, > 0.6 = 낮음). 이미지 없이 단일 신호로 판정하므로 더 보수적인 기준을 적용한다.

#### 세션 간 화면 시퀀스 유사도 (LCS)

- **계산법**: 세션 쌍 간 최장 공통 부분수열(LCS) 길이 / max(시퀀스A 길이, 시퀀스B 길이)의 평균. 세션 쌍이 200개 초과 시 무작위 샘플링한다.
- **의미**: 매 세션에서 같은 순서로 화면을 탐색하는가
- **판정 기준**:

| 범위 | 판정 | 해석 |
|------|------|------|
| > 0.7 | 높음 | 동일 업무 흐름 반복. 대부분의 세션에서 같은 순서로 화면을 탐색한다 |
| 0.5 ~ 0.7 | 중간 | 부분적으로 유사한 흐름이 있으나 변동이 있다 |
| < 0.5 | 낮음 | 세션마다 다른 화면 경로. 정형화된 업무 흐름이 약하다 |

LCS를 사용하는 이유: 공장 업무에서 A->B->C->D 순서가 반복되더라도 특정 상황에서 A->B->D(C 생략)로 수행되는 경우가 있다. LCS는 이런 부분 생략에 관대하면서도 순서를 보존하므로 공장 패턴에 적합하다.

#### 종합 판정

세션 길이 CV와 화면 시퀀스 유사도(LCS) 두 신호를 종합하여 최종 판정을 내린다. 클릭 좌표 집중도는 판정에서 제외된다 (참고용으로만 리포트에 표시).

**일반 모드** (CV + 시퀀스 유사도):

| 판정 | 조건 | 의미 |
|------|------|------|
| **높음** | 2개 신호 모두 "높음" | Vision AI 투입 우선 대상. 자동화 가능한 반복 패턴이 존재할 가능성이 높다 |
| **낮음** | 2개 신호 모두 "낮음" | 자동화 패턴 미약. Vision AI 투입 대상에서 제외 가능 (단, 최종 판단은 사람이 한다) |
| **중간** | 그 외 | 추가 데이터 수집 또는 수동 검토 권장 |

**트리아지 모드** (CV 단독 — 이미지 없이 운영):

| 판정 | 조건 | 의미 |
|------|------|------|
| **높음** | CV < 0.25 | 세션 간 클릭 수가 거의 동일 — 정밀 분석 우선 대상 |
| **중간** | CV 0.25 ~ 0.6 | 추가 확인 필요 |
| **낮음** | CV > 0.6 | 세션 간 편차가 큼 — 일반적인 수동 조작 패턴 |

**판정 방향 원칙 -- False Negative 최소화:**
- 패턴이 있는 장비를 "없음"으로 판정하면 Vision AI 기회 자체를 놓친다 (치명적)
- 패턴이 없는 장비를 "있음"으로 판정하면 Vision 비용 낭비이나 허용 가능
- 따라서 애매한 경우 "중간"으로 판정하여 누락을 방지한다
- 데이터가 부족한(insufficient_data) 신호는 판정에서 제외하되, 모든 신호가 부족한 경우 "중간"으로 판정한다

### 섹션 4 -- 파라미터 민감도 분석 (Layer C)

`--sensitivity-sweep` 옵션을 사용한 경우에만 표시된다.

**Jaccard 유사도 테이블 읽는 법:**

pHash 임계값을 [3, 4, 5, 6]으로 변화시키며, 각 설정에서 선택된 대표 프레임 fname 집합 간의 Jaccard 유사도를 계산한다.

```
Jaccard(A, B) = |A 교집합 B| / |A 합집합 B|
```

- 값이 1.0에 가까울수록 두 설정에서 같은 대표 프레임을 선택했다는 의미
- 값이 0에 가까울수록 설정에 따라 결과가 크게 달라진다는 의미

**임계값 쌍별 비교의 의미:**

테이블의 각 행은 두 임계값 설정 간의 대표 프레임 일치도를 보여준다. 예를 들어 (3, 4) 쌍의 Jaccard가 0.9이면, 임계값을 3으로 하든 4로 하든 대표 프레임의 90%가 동일하다는 의미이다.

**민감도 판정 기준:**

| min(Jaccard) | 판정 | 해석 |
|--------------|------|------|
| > 0.8 | 둔감 (구조 명확) | 파라미터 변경에도 결과가 안정적. 분석 신뢰도가 높다 |
| 0.5 ~ 0.8 | 중간 | 일부 파라미터 조합에서 결과가 달라진다. 중간 신뢰도 |
| < 0.5 | 민감 (구조 모호) | 파라미터에 따라 결과가 크게 달라진다. 추가 검토가 필요하다 |

- **둔감이면**: 해당 장비의 화면 구조가 명확하여 파라미터 선택에 관계없이 일관된 분석이 가능하다
- **민감이면**: 화면 간 pHash 거리가 임계값 근처에 분포하여, 임계값에 따라 화면 그룹핑이 달라진다. 추가 데이터 수집 또는 수동 검토가 필요하다

### 섹션 5 -- 종합 판정

모든 분석 결과를 종합한 최종 판정과 권장 후속 조치를 표시한다.

| 판정 | 의미 | 후속 조치 |
|------|------|-----------|
| **높음** | 자동화 가능한 반복 패턴이 존재할 가능성이 높다 | Vision AI 투입 권장. 우선순위 대상으로 선정한다 |
| **중간** | 패턴이 있을 수 있으나 확신할 수 없다 | 분석 기간 연장 또는 수동 검토. 추가 데이터 수집 후 재분석을 권장한다 |
| **낮음** | 현재 데이터에서 자동화 패턴이 약하다 | Vision AI 투입 대상에서 제외 가능. 단, 최종 판단은 사람이 한다 |

**주의사항:**
- 판정은 자동화 가능 여부의 확정이 아니다. 최종 판단은 반드시 사람이 한다
- "높음" 판정이라도 화면이 반복되는 것이지 의미 있는 업무 패턴인지는 별도 확인이 필요하다
- "낮음" 판정이라도 화면은 동일하지만 입력값만 다른 반복 업무일 수 있다 (pHash로 구분 불가)
- SnapshotScreener의 가치는 "패턴 분석의 답을 주는 것"이 아니라 **Vision AI 전 단계의 비용 절감 도구**로서 존재한다

---

## 8. Cassandra 보호 메커니즘

SnapshotScreener의 모든 동작은 프로덕션 Cassandra 클러스터의 정상 운영에 영향을 주지 않아야 한다. 이를 위해 다음 보호 메커니즘을 적용한다.

### 읽기 전용 접근

Cassandra에 대해 **SELECT 쿼리만 허용**한다. INSERT, UPDATE, DELETE, ALTER, CREATE 등 쓰기/변경 쿼리를 절대 실행하지 않는다. Cassandra 스키마를 변경하지 않는다.

### 포인트 쿼리

모든 Cassandra 쿼리는 **파티션 키 전체를 지정**하는 포인트 쿼리만 사용한다.

- 허용: `WHERE eqpid = ? AND year = ? AND month = ? AND day = ?`
- 금지: 파티션 키 미지정 풀스캔, `ALLOW FILTERING`, 범위 스캔

단일 쿼리로 조회하는 파티션은 항상 1개이다 (장비 1대의 하루치).

### Rate Limiting

| 조회 유형 | 기본 간격 | CLI 파라미터 |
|-----------|-----------|--------------|
| fname 목록 조회 (image 미포함) | 100ms | `--fname-delay-ms` |
| 이미지 포함 조회 | 200ms | `--read-delay-ms` |

### 커넥션 풀 제한

Cassandra 커넥션 풀 크기를 **최대 2**로 제한한다 (`--max-connections`). 병렬 쿼리를 실행하지 않으며, 모든 쿼리는 순차 실행된다.

### 2단계 읽기 전략

Cassandra에서 이미지를 읽는 비용을 최소화하기 위해 모든 분석을 2단계로 나눈다:

```
1단계: fname 목록만 조회 (image 컬럼 제외)
       -> 메타데이터 파싱, 세션 분리, 클릭 클러스터링 수행
       -> Cassandra 부하: 최소

2단계: 대표 프레임으로 선정된 fname에 한해 image 컬럼 조회
       -> pHash 계산, 리포트용 이미지 임베딩
       -> 전체 이미지의 극소수(1~5%)만 읽음
```

### 로컬 pHash 캐시

한 번 읽은 pHash 계산 결과는 로컬 SQLite 캐시에 저장한다. 동일 장비, 동일 날짜에 대한 재분석 시 Cassandra를 다시 읽지 않는다. 캐시 무효화는 `--invalidate-cache` 옵션으로만 수행한다.

### 최초 실행 예상 시간

최초 실행 시에는 모든 이미지의 pHash를 계산해야 하므로 시간이 소요된다:

| 시나리오 | 예상 시간 | 비고 |
|----------|-----------|------|
| 최초 실행 (14일치) | 약 140분 (2시간 20분) | 3,000장/일 x 14일 x 200ms |
| 2회차 이후 (증분) | 약 10분 | 신규 이미지만 처리 |
| 대표 프레임 이미지 조회 | 수 초 | 약 23장 x 200ms |

최초 실행은 프로덕션 부하가 낮은 야간/새벽 시간대에 실행을 권장한다.

---

## 9. 파라미터 튜닝 가이드

### pHash 임계값 조정

**`--phash-similar-threshold` (기본값: 4)**

같은 화면으로 판정하는 pHash distance 임계값이다.

- **올려야 할 때**: 동일한 화면인데 다른 화면 그룹으로 분류되는 경우 (화면 내 작은 변화가 많은 UI)
- **내려야 할 때**: 다른 화면인데 같은 화면 그룹으로 분류되는 경우 (비슷하게 생긴 화면이 많은 UI)
- **확인 방법**: `--sensitivity-sweep`으로 민감도 분석을 실행하여 Jaccard 유사도 확인. 둔감(>0.8)이면 현재 설정이 적절하다

**`--phash-transition-threshold` (기본값: 8)**

화면 전환(전이점)으로 판정하는 pHash distance 임계값이다. `--phash-similar-threshold`보다 항상 높아야 한다.

### 세션 분리 gap 조정

**`--session-gap-ms` (기본값: 900000 = 15분)**

- **늘려야 할 때**: 물리적 작업 후 UI 복귀 등으로 중간에 빈 시간이 생기는 업무 환경. 불필요하게 세션이 분리되는 경우
- **줄여야 할 때**: 빠른 교대 인수인계로 다른 작업자의 세션이 합쳐지는 경우

### DBSCAN eps/min_samples 조정

**`--dbscan-eps` (기본값: 0.03, 정규화 좌표 기준)**

클릭 좌표 클러스터링의 이웃 반경이다. 정규화 좌표(0~1) 기준이므로 해상도에 무관하다.

- **올려야 할 때**: 같은 버튼을 누르는데 클릭 좌표가 조금씩 흔들리는 경우
- **내려야 할 때**: 가까이 있는 다른 버튼들의 클릭이 같은 클러스터로 합쳐지는 경우

**`--dbscan-min-samples` (기본값: 2)**

클러스터로 인정하기 위한 최소 클릭 수이다.

- **올려야 할 때**: 우연히 같은 위치를 2번 클릭한 것을 클러스터로 잡는 경우
- **내려야 할 때**: 소수 클릭이라도 중요한 버튼인 경우

### 분석 기간 가이드라인

하루 약 3,000 스냅샷, 세션 6~15개/일 기준이다.

| 목적 | 필요 기간 | 근거 |
|------|-----------|------|
| pHash 임계값 보정 | 1~2일 | 분포 측정은 1일치로 충분 |
| 일중 패턴 확인 | 3~5일 | 요일 편차 제거, 평일 최소 3일 |
| 주간 패턴 확인 | 2~3주 | 주 단위 반복 여부 확인 |
| 패턴 유무 판정 (안정적) | 4주 | 변동성 흡수, 이상치 제거 |
| Layer C 민감도 분석 | 2주 이상 | 충분한 세션 수(30개 이상) 확보 필요 |

**실질적 시작 기준:** 2주 데이터로 시작하되, 세션 수가 30개 이상 확보되는지를 먼저 확인한다. 세션 수가 충분하면 기간을 늘리지 않아도 된다.

**주의:** 위 기간은 단일 품목 연속 생산 기준이다. 품목 전환이 잦은 라인은 기간을 연장하거나 품목별로 분리하여 분석해야 한다.

---

## 10. 다국어 지원

SnapshotScreener는 한국어(ko)와 영어(en)를 지원한다. `--lang` 옵션 또는 config 파일의 `lang` 키로 설정한다.

```bash
# 영문 출력
snapshot-screener --config config/my_config.yaml --lang en

# 또는 config 파일에서 설정
# lang: en
```

### 적용 범위

| 영역 | 적용 |
|------|------|
| 콘솔 로그 | Phase 진행 메시지, 경고, 에러 메시지 |
| HTML 리포트 | 섹션 제목, 라벨, 판정 문자열, 설명 텍스트 |
| 요약 리포트 | 테이블 헤더, 판정 카드, 권장 사항 |
| 에러 메시지 | Cassandra 연결 실패, 설정 오류 등 |
| JSON 익스포트 | 판정값은 언어 설정과 무관하게 항상 영어 내부키(`high`, `medium`, `low`) 사용 |

### 영문 Windows 환경

영문 Windows의 콘솔 코드페이지(cp1252)는 한글을 지원하지 않는다. `--lang en`으로 설정하면 콘솔에 비-ASCII 문자가 출력되지 않으므로 인코딩 문제가 발생하지 않는다.

---

## 11. 기술 스택

| 기능 | 라이브러리 | 버전 | 비고 |
|------|-----------|------|------|
| Cassandra 조회 | `cassandra-driver` | 3.29+ | SELECT만 사용 |
| pHash 계산 | `Pillow`, `imagehash` | 최신 | pHash 계산 + distance 비교 |
| 설정 파일 | `PyYAML` | 최신 | YAML config 파일 파싱 |
| 클릭 클러스터링 | `scikit-learn`, `numpy` | 최신 | DBSCAN |
| 시퀀스 유사도 | 표준 라이브러리 | - | LCS 직접 구현 (DP, 공간 최적화) |
| pHash 캐시 | `sqlite3` (표준 라이브러리) | - | 로컬 캐시, 추가 설치 불필요 |
| 리포트 생성 | `jinja2` | 3.0+ | HTML 템플릿 렌더링 |
| CLI | `argparse` (표준 라이브러리) | - | 커맨드라인 인터페이스 |
| 분포 시각화 | `matplotlib` | 최신 | 개발/디버깅 시 pHash 분포 확인용 |
| exe 패키징 | `PyInstaller` | 6.0+ | 개발 의존성, 배포용 |

---

## 12. 프로젝트 구조

```
SnapshotScreener/
|-- pyproject.toml                  # 패키지 설정
|-- requirements.txt                # 런타임 의존성
|-- requirements-dev.txt            # 개발 의존성
|-- snapshot_screener/
|   |-- __init__.py
|   |-- __main__.py                 # python -m snapshot_screener 진입점
|   |-- cli.py                      # CLI argparse 정의 및 진입점
|   |-- config.py                   # ScreenerConfig (불변 설정 객체)
|   |-- i18n.py                     # 다국어 번역 (ko/en)
|   |-- models.py                   # 데이터 모델 (SnapshotMeta, FrameFeature 등)
|   |-- pipeline.py                 # 5-Phase 파이프라인 오케스트레이션
|   |-- analysis/
|   |   |-- __init__.py
|   |   |-- session.py              # Phase 3-1: 세션 분리
|   |   |-- screen_group.py         # Phase 3-2: pHash 기반 화면 그룹핑
|   |   |-- clustering.py           # Phase 3-3: DBSCAN 클릭 좌표 클러스터링
|   |   |-- transition.py           # Phase 3-4: 전이점 검출
|   |   |-- selector.py             # Phase 3-5: 대표 프레임 선택
|   |   |-- screening.py            # Phase 3-6: Layer B 스크리닝 신호 계산
|   |   |-- sensitivity.py          # Phase 3-7: Layer C 파라미터 민감도 분석
|   |-- collect/
|   |   |-- __init__.py
|   |   |-- metadata.py             # Phase 1: fname 메타데이터 수집
|   |   |-- phash.py                # Phase 2: pHash 수집 (캐시 우선)
|   |-- db/
|   |   |-- __init__.py
|   |   |-- cassandra_client.py     # Cassandra 클라이언트 (rate limiting 포함)
|   |   |-- cache.py                # SQLite pHash 캐시
|   |-- triage/
|   |   |-- __init__.py
|   |   |-- models.py               # 트리아지 결과 데이터 모델
|   |   |-- csv_loader.py           # 장비 계층 CSV 파싱
|   |   |-- collector.py            # snapshotlist 쿼리 + 톰스톤 회피
|   |   |-- screening.py            # 세션 CV 단독 경량 판정
|   |   |-- pipeline.py             # 트리아지 파이프라인 오케스트레이션
|   |   |-- report.py               # CSV/JSON/HTML 리포트 생성
|   |-- report/
|   |   |-- __init__.py
|   |   |-- image_collector.py      # Phase 4: 대표 프레임 이미지 수집
|   |   |-- image_processor.py      # 클릭 좌표 오버레이 처리
|   |   |-- renderer.py             # Phase 5: HTML 리포트 렌더링
|   |   |-- summary_renderer.py     # 일괄 스크리닝 요약 리포트
|   |-- utils/
|       |-- __init__.py
|       |-- date_range.py           # 날짜 범위 유틸리티
|       |-- fname_parser.py         # fname 파싱 (좌표, timestamp 추출)
|       |-- progress.py             # 로깅 및 진행률 표시
|-- tests/                          # 테스트
```

---

## 13. 용어집

| 용어 | 정의 |
|------|------|
| fname | 스크린샷 파일명. 클릭 좌표(x, y)와 Unix timestamp가 인코딩되어 있다 |
| pHash | Perceptual Hash. 이미지의 시각적 유사도를 비교하기 위한 해시값. 시각적으로 유사한 이미지는 pHash distance가 낮다 |
| pHash distance | 두 pHash 간의 Hamming distance. 값이 낮을수록 이미지가 시각적으로 유사하다 |
| 세션 | 연속된 UI 조작의 단위. 일정 시간 이상 gap이 발생하면 새 세션으로 분리된다 |
| 화면 그룹 | pHash 유사도 기준으로 같은 화면으로 분류된 연속 프레임 집합. 같은 화면을 반복 클릭하는 구간이 하나의 화면 그룹이 된다 |
| 전이점 | 화면 전환, 시간 급증, 클릭 위치 변화 등 조작 흐름의 변곡점. 업무 단계가 전환되는 시점을 나타낸다 |
| 대표 프레임 | 전체 스냅샷에서 업무 흐름을 대표하도록 선별된 프레임. 각 화면 그룹의 첫 프레임과 세션 시작/종료 프레임으로 구성된다 |
| Layer A | Vision AI 입력 축소 기능. 대량 스냅샷에서 대표 프레임만 추출한다 |
| Layer B | 패턴 가능성 사전 스크리닝 기능. 3가지 신호(클릭 집중도, 세션 CV, 시퀀스 유사도)로 패턴 존재 가능성을 판정한다 |
| Layer C | 파라미터 민감도 기반 신뢰도 판정 기능. pHash 임계값을 sweep하여 결과의 안정성을 측정한다 |
| LCS | Longest Common Subsequence (최장 공통 부분수열). 두 시퀀스 간 순서를 보존하는 가장 긴 공통 부분수열이다 |
| Jaccard 유사도 | 두 집합 간 유사도 측정 지표. `|A 교집합 B| / |A 합집합 B|` 로 계산하며, 1에 가까울수록 유사하다 |
| DBSCAN | Density-Based Spatial Clustering of Applications with Noise. 밀도 기반 클러스터링 알고리즘으로, 클릭 좌표의 밀집 영역을 찾는 데 사용한다 |
| CV (변동계수) | Coefficient of Variation. 표준편차를 평균으로 나눈 값으로, 상대적 변동성을 나타낸다 |
| Rate Limiting | Cassandra 쿼리 간 의도적 지연을 두어 부하를 제한하는 메커니즘 |
| 포인트 쿼리 | 파티션 키 전체를 지정하여 단일 파티션만 읽는 쿼리. 풀스캔과 대비되는 개념이다 |
| 트리아지 모드 | 이미지를 읽지 않고 fname 메타데이터만으로 대규모 장비를 경량 스크리닝하는 모드. snapshotlist 테이블(월별 파티션)을 사용하며, 세션 길이 CV 단독으로 판정한다 |
| snapshotlist | 월별 파티션 `(eqpid, year, month)`으로 fname 목록만 저장하는 경량 Cassandra 테이블. image 컬럼 없음, TTL 15일 |
| 회로 차단기 | Circuit Breaker. Cassandra 연속 장애 시 불필요한 retry를 방지하고 조기 중단하는 안전장치 |
| 톰스톤 | Cassandra에서 TTL 만료된 행의 삭제 마커. 읽기 시 스캔 비용을 유발하며, `fname >= ?` 범위 필터로 회피한다 |
