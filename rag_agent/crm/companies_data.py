"""과제용 시드: 공공데이터포털·사업자 정보 및 DART(전자공시) 기업개요를 참고해 편집한 SK 주요 멤버사 20곳.

실제 운영 시에는 data.go.kr API·DART Open API(opendart.fss.or.kr)로 재검증하세요.
사업자등록번호는 국세청 홈택스·bizno 등 공개 조회 결과를 우선합니다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkCompanySeed:
    name: str
    biz_reg_no: str
    address: str
    industry: str
    dart_profile: str
    data_source_note: str


# 업종(industry)은 DART 사업보고서의 업종·주요 사업 문구를 한 줄로 요약(120자 이내).
_SK_SOURCE = (
    "공공데이터포털(data.go.kr) 기업·사업자 정보 및 금융감독원 전자공시(DART) "
    "사업보고서·기업개요를 참고하여 과제 시드로 정리. 식별번호는 공개 조회·공시와 대조 권장."
)

SK_COMPANIES: tuple[SkCompanySeed, ...] = (
    SkCompanySeed(
        name="SK텔레콤",
        biz_reg_no="102-81-42945",
        address="서울특별시 중구 을지로2가 11",
        industry="통신업(이동전화·유선·인터넷 등)",
        dart_profile=(
            "DART 정기공시 기준 국내 대표 이동통신사. 무선·유선·미디어·DX 사업을 영위하며, "
            "전사 디지털 전환 및 B2B ICT 매출 비중 확대가 공시에서 반복 언급됩니다. "
            "유가증권시장 상장사로 분기·사업보고서를 통해 실적·CAPEX·배당 정책이 공개됩니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK하이닉스",
        biz_reg_no="134-86-09483",
        address="경기도 이천시 부발읍 경충대로 2091",
        industry="반도체 제조(메모리 등)",
        dart_profile=(
            "DART에 따르면 DRAM·NAND 등 메모리 반도체를 주력으로 생산·판매하는 글로벌 기업입니다. "
            "설비 투자·공정 미세화·HBM 등 고부가 제품 믹스가 실적 설명의 핵심입니다. "
            "상장사로 분기 실적·CAPEX·환율 민감도가 공시됩니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK이노베이션",
        biz_reg_no="120-86-18821",
        address="서울특별시 종로구 종로 26",
        industry="석유화학·윤활기유·전지소재 등 에너지·화학",
        dart_profile=(
            "DART 사업보고서상 정유·석유화학·윤활·배터리 소재 등 복수 세그먼트를 보유한 지주·사업회사 구조가 "
            "정리되어 있습니다. 그룹 내 에너지·소재 전략과 연계된 투자·스핀오프 이력이 공시에 포함됩니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK바이오사이언스",
        biz_reg_no="124-86-41770",
        address="경기도 성남시 분당구 판교로 310",
        industry="의약품 제조(위탁생산·백신 등)",
        dart_profile=(
            "DART 기업개요에 따르면 백신·바이오 의약품 CMCDO/CDMO 중심 사업을 영위합니다. "
            "글로벌 빅파마 위탁·기술이전 실적이 공시 실적 설명에 자주 등장합니다. "
            "규제·임상·생산 캐파가 리스크 요인으로 기술됩니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK스퀘어",
        biz_reg_no="120-86-63080",
        address="서울특별시 종로구 종로 26",
        industry="지주·투자(반도체·바이오·ICT 등)",
        dart_profile=(
            "DART에 등재된 투자·지주 성격의 회사로, 주요 종속·관계기업 지분가치 변동이 재무제표에 큰 비중을 차지합니다. "
            "반도체·2차전지·플랫폼 등 포트폴리오 재편이 공시 주석에서 설명됩니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK이엔에스",
        biz_reg_no="135-86-01113",
        address="서울특별시 종로구 종로 26",
        industry="가스·전력·열·신재생 등 에너지 솔루션",
        dart_profile=(
            "DART 사업보고서상 LNG·발전·지역난방·신재생 등 에너지 인프라와 B2B 솔루션을 제공하는 사업 구조가 "
            "요약되어 있습니다. 탄소·에너지 전환 정책과 연계한 투자·PPA 등이 공시 논의에 포함됩니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK가스",
        biz_reg_no="138-81-03406",
        address="경기도 성남시 분당구 판교로 227",
        industry="가스 도매·소매 및 관련 설비",
        dart_profile=(
            "DART 기준 LNG·LPG 등 가스 유통과 저장·기화·배관 인프라 사업이 핵심입니다. "
            "에너지 가격·수요 변동과 안전·규제 준수가 공시 리스크로 언급됩니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK네트웍스",
        biz_reg_no="220-81-02568",
        address="서울특별시 종로구 종로 26",
        industry="서비스·유통·호텔·렌터카 등 복합 서비스",
        dart_profile=(
            "DART에 따르면 렌터카·호텔·면세·물류 등 생활 밀착 서비스와 해외 법인을 병행 운영합니다. "
            "계절성·환율·여행 수요가 실적 변동 요인으로 기술되는 경우가 많습니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK지오센트릭",
        biz_reg_no="134-81-00740",
        address="대전광역시 대덕구 신탄진로 122",
        industry="석유화학·소재(플라스틱·합성수지 등)",
        dart_profile=(
            "DART 사업보고서상 정밀화학·소재·친환경·리사이클 전환이 반복되는 테마입니다. "
            "원유·나프타 가격 연동과 글로벌 수요 둔화가 마진에 미치는 영향이 공시에 설명됩니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SKC",
        biz_reg_no="138-81-00312",
        address="경기도 수원시 장안구 경수대로 976",
        industry="필름·소재·2차전지 소재 등",
        dart_profile=(
            "DART 기준 동박·필름 등 소재 사업과 이차전지 소재 확장이 주요 성장 내러티브로 등장합니다. "
            "설비 증설·고객사 검증 주기가 실적 가시성에 영향을 준다는 취지의 공시가 있습니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK실트론",
        biz_reg_no="124-81-02226",
        address="경기도 구리시 갈매순환로 166",
        industry="실리콘 웨이퍼 제조",
        dart_profile=(
            "DART에 따르면 반도체용 실리콘 웨이퍼를 생산하며, 파운드리·메모리 업황과 CAPEX에 연동된 수요가 "
            "실적을 좌우합니다. 품질·수율·가동률이 공시 운영 지표로 다뤄집니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK브로드밴드",
        biz_reg_no="214-86-18758",
        address="서울특별시 중구 퇴계로 24",
        industry="유선·인터넷·방송·IDC 등 통신서비스",
        dart_profile=(
            "DART 기업개요에 유선 인터넷·IPTV·기업용 회선·데이터센터 등이 포함됩니다. "
            "가입자 ARPU·망투자·규제(요금·준공) 이슈가 공시 논의에 자주 등장합니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK오션플랜트",
        biz_reg_no="130-86-08286",
        address="경상남도 거제시 장평로 337",
        industry="해양플랜트·조선 관련 장비",
        dart_profile=(
            "DART 사업보고서상 해양 플랜트·조선 해양 장치 등 프로젝트 단위 매출이 큰 B2B 구조입니다. "
            "선가·원자재·인력·환율이 수익성에 미치는 영향이 공시 리스크로 기술됩니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK엔무브",
        biz_reg_no="120-86-81116",
        address="서울특별시 종로구 우정국로 26",
        industry="윤활유·에너지 솔루션",
        dart_profile=(
            "DART에 따르면 자동차·산업용 윤활제 및 친환경 연료·충전 인프라 등으로 포트폴리오를 확장합니다. "
            "원유 가격·판매 믹스가 마진에 민감하다는 설명이 공시에 있습니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK온",
        biz_reg_no="242-87-02258",
        address="서울특별시 종로구 종로 51",
        industry="이차전지 제조(EV 배터리)",
        dart_profile=(
            "DART 기준 글로벌 완성차 OEM향 EV 배터리 공급·셀·모듈·팩 생산이 핵심입니다. "
            "설비 투자·원재료(양극재 등)·고객사 물량 확정이 실적 가시성을 결정한다는 취지가 공시됩니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK바이오팜",
        biz_reg_no="850-88-01068",
        address="경기도 성남시 분당구 판교로 310",
        industry="의약품 제조·판매(중추신경계 등)",
        dart_profile=(
            "DART에 따르면 자체 개발·라이선스 의약품의 해외 승인·상업화가 실적의 중심입니다. "
            "임상·규제·특허 만료가 공시상 반복되는 리스크 요인입니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK매직",
        biz_reg_no="137-86-01235",
        address="서울특별시 구로구 디지털로 300",
        industry="생활가전·정수기·비데 등 제조·판매",
        dart_profile=(
            "DART 사업보고서상 정수기·주방·위생 가전 등 B2C와 렌탈·유지보수 매출이 혼재합니다. "
            "원가·유통채널·경쟁사 가격이 수익성 논의에 포함됩니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK디스커버리",
        biz_reg_no="102-81-66778",
        address="서울특별시 종로구 종로 26",
        industry="패션·리테일·브랜드 사업",
        dart_profile=(
            "DART 기준 복수 패션·라이프스타일 브랜드와 백화점·아울렛 등 유통을 운영합니다. "
            "계절성·재고·온오프라인 채널 믹스가 실적 설명에 자주 등장합니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK스페셜티",
        biz_reg_no="119-86-31542",
        address="서울특별시 종로구 종로 26",
        industry="특수가스·전자소재 등 정밀소재",
        dart_profile=(
            "DART에 따르면 반도체·디스플레이 공정용 특수가스·전자재료 등 틈새 소재를 다룹니다. "
            "고객사 검증·공급 안정성·규제(안전·환경)가 공시 운영 이슈로 기술됩니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
    SkCompanySeed(
        name="SK플라즈마",
        biz_reg_no="124-81-06111",
        address="경기도 안산시 단원구 시화벤처로 226",
        industry="디스플레이·반도체 부품(진공증착 등)",
        dart_profile=(
            "DART 사업보고서상 FPD·반도체 장비 부품 및 진공·증착 관련 제품군이 중심입니다. "
            "디스플레이 업황·설비 투자 사이클에 매출이 민감하다는 설명이 공시에 있습니다."
        ),
        data_source_note=_SK_SOURCE[:500],
    ),
)


# 고객사별 사업기회: IT 시스템 구축·전환 중심 (제목 접미, project_type, stage)
IT_OPPORTUNITY_TEMPLATES: tuple[tuple[str, str, str], ...] = (
    ("통합 그룹웨어·메신저 클라우드 전환", "협업SW", "니즈확인"),
    ("영업 SFA·CRM 일원화 및 모바일 영업앱", "CRM", "발굴"),
    ("핵심 ERP 리플랫폼(S/4 또는 Oracle) 1차", "ERP", "제안"),
    ("사이버보안 SIEM·SOC 및 제로트러스트 네트워크", "보안", "협상"),
    ("데이터 레이크·레이크하우스 및 경영 BI 포털", "데이터", "발굴"),
    ("M365·Entra ID 전사 표준화 및 IAM 고도화", "M365", "제안"),
    ("SCADA·MES 연계 스마트팩토리 PoC", "SI", "니즈확인"),
    ("OMS·WMS 통합 물류 IT 구축", "물류IT", "발굴"),
    ("고객 채널(웹·앱)·결제·멤버십 플랫폼 리뉴얼", "채널", "협상"),
    ("GenAI 콜센터·챗봇 상담보조 시스템", "AI/ML", "제안"),
    ("레거시 EAI·ESB 현대화 및 API 게이트웨이", "SI", "니즈확인"),
    ("VDI·엔드포인트 통합관리 및 IT자산 CMDB", "인프라", "발굴"),
    ("HR·급여·근태 SaaS 도입 및 온프레 연동", "HCM", "제안"),
    ("B2B 주문·정산 EDI·전자계약 클라우드 전환", "B2B플랫폼", "협상"),
    ("품질·환경 LMS·실험데이터 관리 시스템", "품질IT", "발굴"),
)
