import streamlit as st
import pandas as pd
import google.generativeai as genai
import time
import random
import re

st.set_page_config(page_title="생기부 행특 초안 도우미", page_icon="📝", layout="wide")

st.title("📝 초등 생기부 행특 초안 작성 도우미 (made by 배워서남준이)")
st.subheader("다인수 학급 일괄 처리 버전 (Google Gemini 탑재)")
st.info("아래 안내에 따라 단계별로 천천히 진행해 주세요.")

# --- 세션 상태 초기화 ---
if "result_data" not in st.session_state:
    st.session_state.result_data = None

if "base_df" not in st.session_state:
    st.session_state.base_df = pd.DataFrame({
        "번호": [str(i) for i in range(1, 21)], 
        "관찰 키워드": [""] * 20
    })

if "my_editor" in st.session_state:
    try:
        edits = st.session_state["my_editor"].get("edited_rows", {})
        for row_idx, col_edits in edits.items():
            row_idx = int(row_idx)
            if row_idx < len(st.session_state.base_df):
                for col_name, new_val in col_edits.items():
                    st.session_state.base_df.at[row_idx, col_name] = new_val
    except Exception:
        pass


# ==========================================
# 1️⃣ 1단계: 기본 설정 및 동의
# ==========================================
with st.container(border=True):
    st.markdown("### 1️⃣ 1단계: 기본 설정 및 개인정보 동의")
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_s1, col_s2, col_blank = st.columns([2, 2, 6])
    with col_s1:
        grade_group = st.selectbox("📌 학년군 선택", ["1~2학년군", "3~4학년군", "5~6학년군"])
    with col_s2:
        num_students = st.number_input("👥 총 학생 수", min_value=1, max_value=40, value=len(st.session_state.base_df), step=1)

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

    st.markdown("---")
    st.warning("본 도구는 '초안 작성'을 돕는 보조 도구입니다. 최종 기재 내용은 반드시 교사의 직접 관찰과 판단에 따라 수정되어야 합니다.")
    agree_privacy = st.checkbox("✅ [필수] 위 내용을 확인하였으며, 학생의 실명 등 식별 가능한 개인정보를 직접 입력하지 않겠습니다.")

with st.sidebar.expander("🛠️ 비상용 고급 설정 (클릭)"):
    st.caption("서버의 일일 무료 한도가 초과된 경우, 본인의 API 키를 직접 입력하면 계속 사용할 수 있습니다.")
    user_api_key = st.text_input("🔑 개인 API Key 입력 (선택사항)", type="password")


# ==========================================
# 2️⃣ 2단계: 데이터 입력 및 생성
# ==========================================
if agree_privacy:
    st.markdown("<h2 style='text-align: center; color: #4CAF50;'>⬇️</h2>", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.markdown("### 2️⃣ 2단계: 관찰 키워드 입력 및 자동 생성")
        st.write("아래 두 가지 방법 중 편한 것을 선택하여 키워드를 채워주세요.")
        st.markdown("<br>", unsafe_allow_html=True)

        col_left, col_right = st.columns([1, 2.5])

        with col_left:
            st.info("🗂️ **[방법 1] 엑셀이 편하다면?**\n\n양식을 다운받아 작성 후 올려주세요.")
            
            template_df = pd.DataFrame({"번호": [str(i) for i in range(1, num_students + 1)], "관찰 키워드": [""] * num_students})
            template_csv = template_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📝 1. 맞춤 양식 다운로드",
                data=template_csv,
                file_name=f"행특_입력_양식_{num_students}명.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            uploaded_file = st.file_uploader("📥 2. 파일 업로드 (CSV)", type=["csv"])
            if uploaded_file is not None:
                file_id = uploaded_file.name + str(uploaded_file.size)
                if st.session_state.get('last_uploaded') != file_id:
                    try:
                        try:
                            df = pd.read_csv(uploaded_file, encoding='utf-8')
                        except UnicodeDecodeError:
                            uploaded_file.seek(0)
                            df = pd.read_csv(uploaded_file, encoding='cp949')
                            
                        if "번호" in df.columns and "관찰 키워드" in df.columns:
                            df["번호"] = df["번호"].astype(str)
                            df["관찰 키워드"] = df["관찰 키워드"].fillna("").astype(str)
                            
                            st.session_state.base_df = df
                            st.session_state.last_uploaded = file_id
                            
                            st.success(f"✅ {len(df)}명 업로드 완료!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("🚨 양식이 올바르지 않습니다.")
                    except Exception as e:
                        st.error(f"파일을 읽는 중 에러가 발생했습니다: {e}")

        with col_right:
            st.success("⌨️ **[방법 2] 화면에서 바로 치려면?**\n\n아래 표의 빈칸을 클릭해 직접 입력하거나 고칠 수 있습니다.")
            
            edited_df = st.data_editor(
                st.session_state.base_df,
                key="my_editor",
                column_config={
                    "번호": st.column_config.TextColumn("번호", disabled=True, width=50),
                    "관찰 키워드": st.column_config.TextColumn("관찰 키워드 (예: 산만함, 수학을 좋아함)", max_chars=150, width=1000)
                },
                hide_index=True, use_container_width=True
            )
            st.session_state.base_df = edited_df

        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("🚀 전체 학생 행특 초안 생성하기", use_container_width=True):
            valid_df = edited_df[edited_df["관찰 키워드"].str.strip() != ""]
            if valid_df.empty:
                st.warning("⚠️ 입력된 관찰 키워드가 없습니다.")
                st.stop()
                
            # --- [개선] 진행률 및 안내 문구 세분화 ---
            my_bar = st.progress(5, text="🚀 작업을 준비 중입니다...")
            time.sleep(0.3)
                
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
                        st.error("⚠️ 서버 금고에 API 키가 없습니다. 좌측 메뉴에 개인 키를 입력하세요.")
                        st.stop()
                        
            my_bar.progress(20, text="🌐 구글 서버에 보안 연결을 시도 중입니다...")
            genai.configure(api_key=api_key_to_use)
            time.sleep(0.3)
            
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
                
            my_bar.progress(40, text="🔍 학생 데이터를 분석하고 기재요령 가이드라인을 세팅 중입니다...")
            time.sleep(0.5)
            
            student_batch_text = ""
            for _, row in valid_df.iterrows():
                student_batch_text += f"- [{row['번호']}번 학생] 키워드: {row['관찰 키워드']}\n"
                
            bulk_prompt = f"""
            당신은 대한민국 초등학교 베테랑 교사이자, '2026학년도 학교생활기록부 기재요령'을 완벽히 숙지한 전문가입니다.
            현재 작성 대상은 [{grade_group}] 학생들입니다. 발달 단계에 맞는 초등 교육 전문 어휘를 사용하여 학생당 총 400자 내외로 작성하세요.
            
            [지출 지침: 5대 절대 준수 원칙]
            1. 작성 관점: 학생의 학습, 행동 및 인성 등 학교 교육활동 전반에서 관찰된 특성을 바탕으로 하며, 발전 가능성을 고려한 '학생의 성장을 지원하는 교육적 관점'에서 작성합니다.
            2. 기재 금지 사항 필터링 (Zero Tolerance): 아래 내용은 절대 생성된 텍스트에 포함하지 마십시오.
               - 공인어학시험, 대회 참여 사실 및 수상 실적, 교외상, 인증시험, 영재교육기관 이수
               - 논문, 도서 출간, 지식재산권, 어학연수, 봉사활동 등 해외 활동 실적
               - 부모의 사회·경제적 지위, 장학생·장학금 관련 내용, 특정 대학/기관/상호명, 학교폭력 관련 징계
            3. 팩트 체크 방지: 제공된 키워드를 자연스럽게 연결하되, 주어지지 않은 에피소드나 수치를 지어내지 마십시오.
            4. 문체: 과도한 미사여구 배제. 주어("이 학생은" 등)로 시작하지 말고 곧바로 행동 묘사로 시작. 문장 끝은 명사형 종결어미(~함, ~임, ~돋보임 등)로 마무리.
            5. 긍정적 순화: 부정적인 키워드가 입력되더라도, 성장을 돕는 긍정적이고 발전적인 시선의 표현으로 변환하십시오.
            
            [내용 구성 4단계 로직] (줄바꿈 없는 하나의 자연스러운 문단으로)
            1단계 [학습 태도] -> 2단계 [대인 관계] -> 3단계 [개인적 특성] -> 4단계 [종합 및 기대]
            
            [처리할 학생 리스트]
            {student_batch_text}
            
            [출력 규칙 - 무조건 엄격히 준수]
            결과물을 출력할 때는 반드시 문단 시작 전에 `=== {{번호}}번 ===` 양식의 구분선을 넣으세요.
            인사말이나 부연설명은 절대 하지 마세요.
            """
            
            my_bar.progress(50, text="⚡ AI 서버에 작성을 요청했습니다. (대기열을 통과 중입니다)")
            
            st.markdown("#### ⏳ 실시간 작성 현황")
            
            # --- [개선] 첫 글자 대기 중 안심 안내창 띄우기 ---
            wait_msg = st.warning("⏳ **AI가 머리를 굴리는 중입니다...**\n\n입력하신 키워드를 기재요령에 맞게 분석하고 첫 문장을 구성하기까지 다소 시간이 소요될 수 있습니다. 화면이 멈춘 것이 아니니 잠시만 기다려주세요! 새로고침은 안돼요~")
            
            live_text_box = st.empty() 
            response_text = ""
            
            try:
                response = model.generate_content(bulk_prompt, stream=True)
                
                is_first_chunk = True
                for chunk in response:
                    # 첫 글자가 도착하는 순간 실행되는 마법!
                    if is_first_chunk:
                        wait_msg.empty() # 노란색 경고창을 즉시 지워버립니다.
                        my_bar.progress(65, text="✍️ 텍스트 작성을 시작했습니다! 아래 상자를 확인하세요.")
                        is_first_chunk = False
                        
                    response_text += chunk.text
                    live_text_box.info(response_text) 
                    
            except Exception as e:
                error_msg = str(e).lower()
                # 429 에러(한도 초과)를 감지하면 친절한 안내문 출력
                if "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg:
                    st.error("🚨 **서버의 일일 무료 사용량이 초과되어 잠시 멈췄습니다!**\n\n왼쪽 사이드바의 **[🛠️ 비상용 고급 설정]** 칸에 선생님의 **개인 API 키**를 입력하시면 지금 바로 이어서 정상 작동합니다. (새로고침하지 마시고 키만 입력 후 생성 버튼을 다시 눌러주세요!)")
                else:
                    # 다른 알 수 없는 에러일 경우 기존처럼 출력
                    st.error(f"작성 중 알 수 없는 에러가 발생했습니다: {e}")
                st.stop()
                
            my_bar.progress(85, text="📝 작성이 완료되었습니다! 표 형식으로 예쁘게 정리 중입니다...")
            time.sleep(1)
            live_text_box.empty()
                
            result_df = edited_df.copy()
            result_df["생성된 행특 초안 (결과)"] = ""
            
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
                    result_df.loc[result_df["번호"] == str_num, "생성된 행특 초안 (결과)"] = text.replace("*", "").strip()
                    
            st.session_state.result_data = result_df
            my_bar.progress(100, text="🎉 모든 작업이 성공적으로 완료되었습니다!")
            time.sleep(1)
            my_bar.empty()

else:
    st.info("💡 1단계의 '[필수] 개인정보 보호 동의'에 체크(✅)하시면 2단계 입력창이 나타납니다.")


# ==========================================
# 3️⃣ 3단계: 결과 확인 및 다운로드
# ==========================================
if st.session_state.result_data is not None:
    st.markdown("<h2 style='text-align: center; color: #4CAF50;'>⬇️</h2>", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.markdown("### 3️⃣ 3단계: 결과 확인 및 최종 다운로드")
        st.success("🎉 초안 생성이 완료되었습니다! 최종 나이스(NEIS) 입력 전, 아래 체크리스트를 확인해 주세요.")
        
        st.markdown("#### 🔍 교사 최종 검토 체크리스트")
        st.info("💡 기재요령 준수를 위해 아래 4개 항목을 모두 체크(✅)하셔야 엑셀 다운로드 버튼이 활성화됩니다.")
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            check1 = st.checkbox("1. 교사가 직접 관찰한 내용인가요?")
            check2 = st.checkbox("2. 학생의 실명 등 민감한 개인정보가 들어가지 않았나요?")
        with col_c2:
            check3 = st.checkbox("3. 학생의 특성이 과장되거나 사실과 다르게 표현되지 않았나요?")
            check4 = st.checkbox("4. 기재 금지어(대회, 수상, 영재원, 부모 직업 등)가 없나요?")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.dataframe(
            st.session_state.result_data, 
            column_config={
                "번호": st.column_config.TextColumn("번호", width=50),
                "생성된 행특 초안 (결과)": st.column_config.TextColumn("생성된 행특 초안 (결과)", width=1000)
            },
            hide_index=True, 
            use_container_width=True
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if check1 and check2 and check3 and check4:
            csv_data = st.session_state.result_data.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 결과 엑셀(CSV) 파일로 전체 다운로드", 
                data=csv_data, 
                file_name="생기부_행특_초안_일괄생성_결과.csv", 
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.warning("🔒 다운로드 잠금: 위 체크리스트 4개를 모두 확인해주세요.")
