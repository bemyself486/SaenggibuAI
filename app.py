import streamlit as st
import pandas as pd
import google.generativeai as genai
import time
import random
import re

st.set_page_config(page_title="생기부 행특 자동화", page_icon="📝", layout="wide")

st.title("📝 초등 생기부 행특 일괄 자동화 시스템")
st.subheader("다인수 학급 일괄 처리 버전 (Google Gemini 탑재)")

st.info("학년군과 학생수를 설정하고 키워드를 입력하면, 전체 학급 학생의 행특을 한 번에 생성합니다. (비용: 무료)")

if "result_data" not in st.session_state:
    st.session_state.result_data = None

# [핵심 1] 엎어치기, 복사하기 등 복잡한 코드를 싹 지우고 오직 '원본 도화지' 하나만 둡니다.
if "base_df" not in st.session_state:
    st.session_state.base_df = pd.DataFrame({
        "번호": [str(i) for i in range(1, 21)], 
        "관찰 키워드": [""] * 20
    })

st.sidebar.header("⚙️ 기본 설정")
grade_group = st.sidebar.selectbox("학년군을 선택하세요", ["1~2학년군", "3~4학년군", "5~6학년군"])

num_students = st.sidebar.number_input("총 학생 수를 입력하세요", min_value=1, max_value=40, value=len(st.session_state.base_df), step=1)

# [핵심 2] 인원수가 바뀌면 도화지의 꼬리 부분만 고무줄처럼 덧붙이거나 잘라냅니다.
current_len = len(st.session_state.base_df)
if num_students > current_len:
    extra_count = num_students - current_len
    extra_df = pd.DataFrame({
        "번호": [str(i) for i in range(current_len + 1, num_students + 1)],
        "관찰 키워드": [""] * extra_count
    })
    st.session_state.base_df = pd.concat([st.session_state.base_df, extra_df], ignore_index=True)
elif num_students < current_len:
    st.session_state.base_df = st.session_state.base_df.iloc[:num_students]

with st.sidebar.expander("🛠️ 비상용 고급 설정 (클릭)"):
    st.caption("사용자가 몰려 서버의 일일 무료 한도가 초과된 경우, 본인의 API 키를 직접 입력하면 계속 사용할 수 있습니다.")
    user_api_key = st.text_input("🔑 개인 API Key 입력 (선택사항)", type="password")

def get_system_prompt(grade_group):
    return f"""
    당신은 대한민국 초등학교 베테랑 교사이자, '2026학년도 학교생활기록부 기재요령'을 완벽히 숙지한 전문가입니다.
    제공된 학생들의 관찰 키워드를 바탕으로, 행동특성 및 종합의견(행특)을 지침에 맞게 작성해야 합니다.

    [지출 지침: 5대 절대 준수 원칙]
    1. 작성 관점: 학생의 학습, 행동 및 인성 등 학교 교육활동 전반에서 관찰된 특성을 바탕으로 하며, 학생의 성장 정도, 특기사항, 발전 가능성을 고려한 '학생의 성장을 지원하는 교육적 관점'에서 작성합니다.
    2. 기재 금지 사항 필터링 (Zero Tolerance): 아래 내용은 사용자가 키워드로 입력하더라도 절대 생성된 텍스트에 포함하지 마십시오.
       - 각종 공인어학시험, 교내·외 대회 참여 사실 및 수상 실적, 교외상, 교내·외 인증시험
       - 영재교육기관(영재학교, 영재학급, 영재교육원) 이수 관련 내용
       - 논문 투고, 도서 출간, 지식재산권 출원·등록 사실
       - 어학연수, 봉사활동 등 해외 활동 실적
       - 부모(친인척 포함)의 사회·경제적 지위(직종명, 직장명, 직위명 등) 암시 내용
       - 장학생·장학금 관련 내용
       - 구체적인 특정 대학명, 기관명, 상호명, 강사명
       - 학교폭력과 관련된 징계 및 조치 사항
    3. 팩트 체크 및 할루시네이션 방지: 제공된 키워드를 자연스러운 문장으로 연결하되, 주어지지 않은 구체적인 에피소드나 수치, 평가 결과를 임의로 지어내지 마십시오.
    4. 문체 및 어조:
       - 철저하게 객관적인 관찰자 시점을 유지하고, 과도한 미사여구나 감정적인 표현은 철저히 배제합니다.
       - [주어 생략]: 문장의 시작을 "이 학생은", "학생은", "OOO은" 같은 주어로 절대 시작하지 마십시오. 곧바로 행동 특성 묘사로 자연스럽게 시작하십시오.
       - 문장의 끝은 반드시 '~함', '~임', '~모습이 돋보임', '~태도를 지님', '~할 것으로 기대됨' 등 명사형 종결어미로 마무리합니다.
    5. 긍정적 순화(우회) 원칙: 부정적인 키워드(예: 산만함, 고집)가 입력되더라도, 이를 학생의 성장 가능성과 교사의 발전적인 시선이 담긴 긍정적 표현으로 변환하십시오. 

    [내용 구성 로직 (STRUCTURE)]
    생성되는 텍스트는 반드시 다음 4단계의 구조가 '줄바꿈 없는 하나의 자연스러운 문단'으로 이어지도록 작성하세요. 
    1단계 [학습 태도]: 수업 참여도, 자기주도적 학습에 의한 변화와 성장 정도
    2단계 [대인 관계]: 교우 관계, 배려심, 협동심, 갈등 해결 능력
    3단계 [개인적 특성]: 학생만의 고유한 장점, 성격, 인성, 책임감
    4단계 [종합 및 기대]: 한 학년 동안의 총평과 향후 성장 가능성(기대되는 점)

    현재 작성 대상은 [{grade_group}] 학생들입니다. 발달 단계에 맞는 초등 교육 전문 어휘를 사용하여 학생당 총 400자 내외로 작성하세요. 부연 설명 없이 오직 결과만 출력하세요.
    """

st.markdown("### 📋 학생별 관찰 키워드 입력표")

# [핵심 3] 고정된 이름표(key="student_table")를 달아주어, 인원수가 바뀌어도 스트림릿이 타자 치던 내용을 놓치지 않게 합니다!
edited_df = st.data_editor(
    st.session_state.base_df,
    key="student_table",
    column_config={
        "번호": st.column_config.TextColumn("번호", disabled=True, width=50),
        "관찰 키워드": st.column_config.TextColumn("관찰 키워드 (예: 산만함, 수학을 좋아함)", max_chars=150, width=1000)
    },
    hide_index=True, use_container_width=True
)

st.markdown("---")

if st.button("🚀 전체 학생 행특 생성하기"):
    valid_df = edited_df[edited_df["관찰 키워드"].str.strip() != ""]
    if valid_df.empty:
        st.warning("⚠️ 입력된 관찰 키워드가 없습니다.")
        st.stop()
        
    progress_text = "🚀 작업을 준비 중입니다..."
    my_bar = st.progress(0, text=progress_text)
        
    api_key_to_use = None
    if user_api_key:
        api_key_to_use = user_api_key
        st.info("✅ 개인 API 키로 구동됩니다.")
    else:
        try:
            server_keys = st.secrets["GEMINI_API_KEYS"]
            api_key_to_use = random.choice(server_keys)
        except:
            try:
                api_key_to_use = st.secrets["GEMINI_API_KEY"]
            except:
                st.error("⚠️ 서버 금고에 API 키가 없습니다. 비상용 메뉴에 개인 키를 입력하세요.")
                st.stop()
                
    my_bar.progress(20, text="🌐 구글 서버에 연결 중입니다...")
    genai.configure(api_key=api_key_to_use)
    
    try:
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        target_model = None
        for m_name in available_models:
            if '1.5-flash' in m_name:
                target_model = m_name
                break
                
        if not target_model:
            target_model = available_models[0]
            
        model = genai.GenerativeModel(target_model)
        
    except Exception as e:
        st.error(f"구글 서버 연결 중 에러가 발생했습니다: {e}")
        st.stop()
        
    student_batch_text = ""
    for _, row in valid_df.iterrows():
        student_batch_text += f"- [{row['번호']}번 학생] 키워드: {row['관찰 키워드']}\n"
        
    bulk_prompt = get_system_prompt(grade_group) + f"""
    
    [처리할 학생 리스트]
    {student_batch_text}
    
    [출력 규칙 - 무조건 엄격히 준수]
    위 학생들의 키워드를 바탕으로 각각 지침을 반영한 행특 문단을 생성하세요.
    각 학생의 결과물을 출력할 때는 반드시 문단 시작 전에 `=== {{번호}}번 ===` 양식의 구분선을 넣으세요.
    인사말이나 부연설명은 절대 하지 말고 오직 아래 예시 양식만 완벽히 지켜서 출력하세요.
    
    예시:
    === 1번 ===
    학습에 임하는 태도가 진지하며 교과 활동에 주도적으로 참여함. 친구들의 의견을 경청하고...
    === 2번 ===
    평소 주위 친구들을 배려하고 협동하는 태도가 돋보임. 과제 해결에 책임감이 강하며...
    """
    
    my_bar.progress(50, text="⚡ AI가 기재요령을 검토하며 일괄 작성 중입니다. (새로고침은 하지 말고 기다려주세요)")
    
    try:
        response = model.generate_content(bulk_prompt)
        response_text = response.text
    except Exception as e:
        st.error(f"작성 중 에러가 발생했습니다: {e}")
        st.stop()
        
    my_bar.progress(80, text="📝 작성이 완료되었습니다! 표 형식으로 예쁘게 정리 중입니다...")
        
    result_df = edited_df.copy()
    result_df["생성된 행특 (결과)"] = ""
    
    parsed_results = {}
    current_num = None
    current_text = []
    
    for line in response_text.split("\n"):
        match = re.search(r'===\s*(\d+)\s*번\s*===', line)
        if match:
            if current_num is not None:
                parsed_results[current_num] = "\n".join(current_text).strip()
            current_num = int(match.group(1))
            current_text = []
        else:
            if current_num is not None:
                current_text.append(line)
                
    if current_num is not None:
        parsed_results[current_num] = "\n".join(current_text).strip()
        
    for num, text in parsed_results.items():
        str_num = str(num)
        if str_num in result_df["번호"].values:
            result_df.loc[result_df["번호"] == str_num, "생성된 행특 (결과)"] = text.replace("*", "").strip()
            
    st.session_state.result_data = result_df
    my_bar.progress(100, text="🎉 모든 작업이 성공적으로 완료되었습니다!")
    time.sleep(1)
    my_bar.empty()

if st.session_state.result_data is not None:
    st.success("🎉 생성 완료! 표의 내용을 확인하시고 엑셀 파일로 꼭 다운로드하세요.")
    
    st.dataframe(
        st.session_state.result_data, 
        column_config={
            "번호": st.column_config.TextColumn("번호", width=50),
            "생성된 행특 (결과)": st.column_config.TextColumn("생성된 행특 (결과)", width=1000)
        },
        hide_index=True, 
        use_container_width=True
    )
    
    csv_data = st.session_state.result_data.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 엑셀(CSV) 파일로 전체 다운로드", 
        data=csv_data, 
        file_name="생기부_행특_일괄생성_결과.csv", 
        mime="text/csv"
    )
