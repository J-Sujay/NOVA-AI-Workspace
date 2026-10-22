import csv, io, re
from datetime import datetime
from html import escape
import streamlit as st

st.set_page_config(page_title="NOVA | AI Workspace", page_icon="✨", layout="wide")
try:
    from chatbot import get_response, get_database_status, get_recent_conversations, answer_from_document, analyze_sentiment, document_knowledge
    BACKEND_ERROR = None
except Exception as exc:
    BACKEND_ERROR = exc
    get_response = get_database_status = get_recent_conversations = answer_from_document = analyze_sentiment = None
    document_knowledge = ""

for k,v in {"nova_page":"Overview","nova_theme":"Light","nova_messages":[],"nova_last_prompt":"","nova_uploaded_name":"","nova_uploaded_text":"","nova_pending_prompt":"","nova_notice":""}.items():
    if k not in st.session_state: st.session_state[k]=v

def go(p): st.session_state.nova_page=p
def theme(t): st.session_state.nova_theme=t
def new_chat():
    st.session_state.nova_messages=[]; st.session_state.nova_last_prompt=""
    st.session_state.nova_notice="New chat started. Saved history was preserved."
def clear_chat():
    st.session_state.nova_messages=[]
    st.session_state.nova_notice="Visible chat cleared; MySQL records were not deleted."

def clear_sentiment():
    # Streamlit runs this callback before recreating the text-area widget.
    st.session_state["sentiment_text"] = ""

def suggest(p):
    st.session_state.nova_pending_prompt=p; st.session_state.nova_page="AI Conversation"
def exchange(p,r):
    now=datetime.now().strftime("%I:%M %p")
    st.session_state.nova_messages.extend([{"role":"user","content":p,"time":now},{"role":"assistant","content":r,"time":now}])
    st.session_state.nova_last_prompt=p
def process(p):
    p=str(p).strip()
    if not p: st.warning("Please enter a message."); return
    if BACKEND_ERROR: st.error("Backend could not load. Check chatbot.py and dependencies."); return
    with st.spinner("NOVA is thinking…"):
        try: r=get_response(p)
        except Exception as e: r=f"NOVA couldn't process this request ({type(e).__name__}). Check the PowerShell terminal."
    exchange(p,r)
def regenerate():
    p=st.session_state.nova_last_prompt
    if not p: st.session_state.nova_notice="No response to regenerate."; return
    st.session_state.nova_messages=st.session_state.nova_messages[:-2]
    try: exchange(p,get_response(p)); st.session_state.nova_notice="Response regenerated."
    except Exception as e: st.session_state.nova_notice=f"Regeneration failed ({type(e).__name__})."

dark=st.session_state.nova_theme=="Dark"
C={"bg":"#0b1428","panel":"#101e35","panel2":"#152844","text":"#f5f8ff","muted":"#b6c6e2","border":"#2b4264","input":"#0d1a30"} if dark else {"bg":"#f5f9ff","panel":"#fff","panel2":"#f1f6ff","text":"#0b1b50","muted":"#52658e","border":"#dce8fb","input":"#fff"}
st.markdown(f"""
<style>
:root{{--bg:{C['bg']};--panel:{C['panel']};--p2:{C['panel2']};--text:{C['text']};--muted:{C['muted']};--border:{C['border']};}}
.stApp{{background:var(--bg);color:var(--text)}} [data-testid="stHeader"]{{background:transparent}}
[data-testid="stAppViewContainer"] .main .block-container{{max-width:1800px;padding:1rem 1.2rem 2rem}}
h1,h2,h3,h4,p,label,li{{color:var(--text)}} [data-testid="stSidebar"]{{background:linear-gradient(180deg,var(--panel),var(--p2));border-right:1px solid var(--border)}}
.nbrand{{display:flex;gap:12px;align-items:center;padding:8px 4px 24px}} .nmark{{width:54px;height:54px;border-radius:18px;display:grid;place-items:center;color:white;font-size:30px;background:linear-gradient(135deg,#00c9f5,#2375ff 55%,#a52cff)}}
.nbrand b{{font-size:27px;letter-spacing:1px;color:var(--text)}} .muted{{font-size:12px;line-height:1.55;color:var(--muted)}}
.hero{{border:1px solid #bde6ff;border-radius:22px;padding:26px 28px;min-height:205px;position:relative;overflow:hidden;background:radial-gradient(circle at 83% 45%,#c9b8ff 0,transparent 29%),radial-gradient(circle at 65% 100%,#a5efff 0,transparent 34%),linear-gradient(110deg,#f1fcff,#e7f4ff 50%,#f2edff)}}
.hero .eyebrow{{font-size:11px;letter-spacing:4px;font-weight:900;color:#058dc9}} .hero h1{{font-size:clamp(30px,3vw,49px);line-height:1.05;margin:5px 0;color:#0c1c50;font-weight:900}}
.grad{{background:linear-gradient(90deg,#05aeea,#4e50ff,#a02ce8);-webkit-background-clip:text;background-clip:text;color:transparent}} .hero h2{{font-size:clamp(20px,2vw,31px);margin:0 0 12px;color:#263b75}}
.hero p{{max-width:700px;font-size:14px;line-height:1.65;color:#344c82}} .robot{{position:absolute;right:5%;bottom:-14px;font-size:105px}}
.panel{{background:var(--panel);border:1px solid var(--border);border-radius:18px;padding:16px;margin-bottom:12px;box-shadow:0 7px 24px #416bb10a}}
.title{{font-size:18px;font-weight:900;color:var(--text);margin-bottom:3px}} .msg{{border:1px solid var(--border);border-radius:15px;background:var(--p2);padding:12px 14px;margin:7px 0 12px;line-height:1.65;overflow-wrap:anywhere}}
.metric{{border:1px solid var(--border);border-radius:13px;padding:12px;background:var(--p2)}} .metric b{{font-size:22px;color:var(--text)}} .metric small{{color:var(--muted)}}
.stButton>button{{border:1px solid var(--border);border-radius:12px;min-height:40px;background:var(--panel);color:var(--text);font-weight:750;transition:transform .16s,box-shadow .16s}}
.stButton>button:hover{{border-color:#08b8ee;box-shadow:0 5px 16px #268cff22;transform:translateY(-1px);color:var(--text)}} .stButton>button:focus{{outline:2px solid #08b8ee;outline-offset:2px}}
.stButton>button[kind="primary"]{{background:linear-gradient(100deg,#00bff0,#287aff 58%,#9238f5);color:white;border:0}}
div[data-testid="stTextInput"] input,div[data-testid="stTextArea"] textarea{{background:var(--input);color:var(--text);border-color:var(--border);border-radius:12px}}
[data-testid="stChatMessage"]{{background:var(--p2);border:1px solid var(--border);border-radius:15px}} hr{{border-color:var(--border)}}
</style>""",unsafe_allow_html=True)

db_ok=False
if not BACKEND_ERROR:
    try: db_ok,db_status=get_database_status()
    except Exception: db_status="Database unavailable"

with st.sidebar:
    st.markdown('<div class="nbrand"><div class="nmark">✦</div><div><b>NOVA</b><div class="muted">AI WORKSPACE</div></div></div>',unsafe_allow_html=True)
    st.caption("WORKSPACE")
    for p,ic in [("Overview","⌂"),("AI Conversation","☏"),("Document Q&A","▤"),("Sentiment Analysis","▥"),("MySQL History","▤")]:
        st.button(f"{ic}  {p}",key="nav_"+p,type="primary" if st.session_state.nova_page==p else "secondary",use_container_width=True,on_click=go,args=(p,))
    st.divider(); st.caption("THEME")
    a,b=st.columns(2)
    with a: st.button("☀ Light",key="light",use_container_width=True,type="primary" if not dark else "secondary",on_click=theme,args=("Light",))
    with b: st.button("☾ Dark",key="dark",use_container_width=True,type="primary" if dark else "secondary",on_click=theme,args=("Dark",))
    st.divider(); st.caption("SYSTEM STATUS")
    st.markdown('<div>🟢 Streamlit Interface <b style="float:right">Active</b></div>',unsafe_allow_html=True)
    st.markdown(f'<div style="margin-top:10px">📄 Knowledge Base <b style="float:right">{ "Loaded" if document_knowledge else "Missing"}</b></div>',unsafe_allow_html=True)
    st.markdown(f'<div style="margin-top:10px">🗄️ MySQL <b style="float:right">{ "Connected" if db_ok else "Unavailable"}</b></div>',unsafe_allow_html=True)
    if st.button("＋ New Conversation",key="new",type="primary",use_container_width=True): new_chat(); go("AI Conversation"); st.rerun()
    if st.button("▤ Clear Chat",key="clear",use_container_width=True): clear_chat(); st.rerun()
    st.markdown('<div class="panel" style="margin-top:30px"><b>🔵 NOVA</b><div class="muted">Your AI Assistant</div></div>',unsafe_allow_html=True)

if st.session_state.nova_notice: st.toast(st.session_state.nova_notice); st.session_state.nova_notice=""
st.markdown(f'<div class="muted">✦ NOVA AI WORKSPACE　 •　 {datetime.now().strftime("%a, %d %b %Y · %I:%M %p")} <span style="float:right">🟣 Sujay</span></div>',unsafe_allow_html=True)

def hero():
    st.markdown('<div class="hero"><div class="eyebrow">YOUR INTELLIGENT ASSISTANT</div><h1>Meet <span class="grad">NOVA.</span></h1><h2><span style="color:#06aeea">Think clearly.</span> <span class="grad">Work smarter.</span></h2><p>A smart AI workspace for conversations, document questions, text sentiment analysis,<br>and saved history — built to turn your questions into meaningful insights.</p><div class="robot">🤖</div></div>',unsafe_allow_html=True)

def chat():
    st.markdown('<div class="title">💬 AI Conversation</div><div class="muted">Chat with NOVA. Ask questions, get explanations, or choose a suggested prompt.</div>',unsafe_allow_html=True)
    if not st.session_state.nova_messages:
        st.markdown('<div class="msg"><b>✨ NOVA</b><br>Hi Sujay! 👋<br>I’m NOVA, your intelligent AI assistant. I can help answer questions, analyze documents, perform basic sentiment analysis, and explore saved history.<br><br>What would you like to explore today?</div>',unsafe_allow_html=True)
    for i,m in enumerate(st.session_state.nova_messages):
        with st.chat_message("assistant" if m["role"]=="assistant" else "user",avatar="✨" if m["role"]=="assistant" else "👤"):
            st.markdown(m["content"]); st.caption(m.get("time",""))
            if m["role"]=="assistant":
                st.download_button("↓ Save response",m["content"],"nova_response.txt","text/plain",key=f"save_{i}")
                st.button("↻ Regenerate",key=f"regen_{i}",disabled=i!=len(st.session_state.nova_messages)-1,on_click=regenerate)
    with st.form("send_form",clear_on_submit=True):
        x,y=st.columns([8,1])
        with x: prompt=st.text_input("Message",placeholder="Message NOVA…",label_visibility="collapsed")
        with y: send=st.form_submit_button("➤ Send",type="primary",use_container_width=True)
        if send: process(prompt); st.rerun()
    if st.session_state.nova_pending_prompt:
        p=st.session_state.nova_pending_prompt; st.session_state.nova_pending_prompt=""; process(p); st.rerun()

def right_panel():
    st.markdown(f'<div class="panel"><div class="title">✦ System Status</div><div class="muted">🟢 Streamlit interface active</div><div class="muted">{"🟢 Backend ready" if not BACKEND_ERROR else "🟠 Backend needs attention"}</div><div class="muted">{"🟢 MySQL connected" if db_ok else "🟠 MySQL unavailable"}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="panel"><div class="title">💡 Suggested Prompts</div>',unsafe_allow_html=True)
    for label,p in [("What can you do?","What can you do?"),("Explain data analytics simply","Explain data analytics simply"),("Summarize the knowledge document","document: summarize all information"),("Analyze sample sentiment","sentiment: I am happy with this project")]:
        st.button(label,key="s_"+label,use_container_width=True,on_click=suggest,args=(p,))
    st.markdown('</div><div class="panel"><div class="title">🕘 Recent Conversations</div>',unsafe_allow_html=True)
    if db_ok:
        try:
            rows,err=get_recent_conversations(5)
            if rows:
                for row in rows: st.markdown(f'<div class="msg" style="padding:8px;margin:6px 0"><b>{escape(str(row.get("user_message",""))[:48])}</b><br><span class="muted">{escape(str(row.get("created_at","")))}</span></div>',unsafe_allow_html=True)
            else: st.caption("Saved conversations will appear here.")
        except Exception:
            st.caption("History temporarily unavailable.")
    else:
        st.caption("Connect MySQL to view saved history.")
    st.markdown('</div><div class="panel"><div class="title">💡 Tips for Better Results</div><div class="muted">✅ Be clear and specific<br>✅ Ask one question at a time<br>✅ Try example prompts<br>✅ Explore each feature</div></div>',unsafe_allow_html=True)

p=st.session_state.nova_page
if p=="Overview":
    hero(); st.write("")
    x,y=st.columns([4,1])
    with x: st.markdown('<div class="title">⚡ Quick Actions</div><div class="muted">Start a conversation or try one of the suggestions below.</div>',unsafe_allow_html=True)
    with y: st.markdown('<div style="text-align:right;color:#00a86b;font-weight:800">● WORKSPACE ACTIVE</div>',unsafe_allow_html=True)
    cards=st.columns(4)
    for col,(ic,title,desc,target,bg) in zip(cards,[("💬","Ask Anything","Get instant answers with AI","AI Conversation","#e1f7ff"),("📄","Analyze Documents","Ask questions about files","Document Q&A","#f0e2ff"),("▥","Check Sentiment","Analyze text sentiment","Sentiment Analysis","#dcfff1"),("🗄️","View History","Explore saved chats","MySQL History","#fff0d2")]):
        with col:
            st.markdown(f'<div class="panel" style="min-height:126px;background:linear-gradient(140deg,{bg},var(--panel))"><div style="font-size:27px">{ic}</div><b>{title}</b><div class="muted">{desc}</div></div>',unsafe_allow_html=True)
            st.button("Open →",key="open_"+target,use_container_width=True,on_click=go,args=(target,),type="primary" if target=="AI Conversation" else "secondary")
    x,y=st.columns([2.35,1])
    with x: st.markdown('<div class="panel">',unsafe_allow_html=True); chat(); st.markdown('</div>',unsafe_allow_html=True)
    with y:
        st.markdown(f'<div class="panel"><div class="metric"><b>{len(st.session_state.nova_messages)//2}</b><br><small>Chats this session</small></div><br><div class="metric"><b>{"Loaded" if document_knowledge else "Missing"}</b><br><small>Knowledge base</small></div></div>',unsafe_allow_html=True); right_panel()
elif p=="AI Conversation":
    hero(); x,y=st.columns([2.35,1])
    with x: st.markdown('<div class="panel">',unsafe_allow_html=True); chat(); st.markdown('</div>',unsafe_allow_html=True)
    with y: right_panel()
elif p=="Document Q&A":
    st.markdown('<div class="title">📄 Document Q&A</div><div class="muted">Ask about the knowledge file or upload TXT, Markdown, or CSV for temporary keyword-based Q&A.</div>',unsafe_allow_html=True)
    up=st.file_uploader("Upload text document",type=["txt","md","csv"])
    if up:
        try: st.session_state.nova_uploaded_text=up.getvalue().decode("utf-8-sig"); st.session_state.nova_uploaded_name=up.name; st.success(f"Loaded {up.name} for this session.")
        except UnicodeDecodeError: st.error("Please upload UTF-8 text.")
    if st.session_state.nova_uploaded_name:
        st.caption("Current file: "+st.session_state.nova_uploaded_name)
        if st.button("Remove uploaded document"): st.session_state.nova_uploaded_text=""; st.session_state.nova_uploaded_name=""; st.rerun()
    q=st.text_area("Your question", placeholder="What would you like to know?", key="document_question")
    if st.button("🔎 Find answer",type="primary"):
        if not q.strip(): st.warning("Enter a question first.")
        elif st.session_state.nova_uploaded_text:
            lines=[l.strip() for l in st.session_state.nova_uploaded_text.splitlines() if l.strip()]
            stop={"what","which","does","the","and","for","are","how","can","you","about","from","this","that"}
            terms={t.lower() for t in re.findall(r"\b[\w'-]{3,}\b",q) if t.lower() not in stop}
            rank=sorted(((sum(t in set(re.findall(r"\b[\w'-]+\b",l.lower())) for t in terms),l) for l in lines),reverse=True)
            matches=[l for s,l in rank if rank and s>0 and s==rank[0][0]][:8]
            st.write("\n\n".join("• "+l for l in matches) if matches else "No strong keyword match. Try other terms.")
        elif not BACKEND_ERROR: st.write(answer_from_document(q))
        else: st.error("Backend unavailable.")
    with st.expander("View built-in knowledge document"): st.text(document_knowledge or "Knowledge file missing.")
elif p=="Sentiment Analysis":
    st.markdown('<div class="title">▥ Sentiment Analysis</div><div class="muted">Estimate sentiment with the existing word-based analyzer.</div>',unsafe_allow_html=True)
    text=st.text_area("Text to analyze",height=180,placeholder="Paste a review or feedback…",key="sentiment_text")
    x,y=st.columns([1,4])
    with x: run=st.button("Analyze sentiment",type="primary")
    with y:
        st.button(
            "Clear text",
            key="clear_sentiment",
            on_click=clear_sentiment
        )
    if run:
        if not text.strip(): st.warning("Enter some text first.")
        elif BACKEND_ERROR: st.error("Backend unavailable.")
        else: st.markdown('<div class="panel"><div class="title">Result</div></div>',unsafe_allow_html=True); st.markdown(analyze_sentiment(text)); st.caption("Word-based estimate, not a trained ML model.")
    st.info("This analyzer counts predefined positive/negative words; context, sarcasm and negation may be missed.")
elif p=="MySQL History":
    st.markdown('<div class="title">🗄️ MySQL History</div><div class="muted">Review conversations saved by your backend.</div>',unsafe_allow_html=True)
    if not db_ok:
        st.warning("MySQL unavailable. Check that it is running and your local .env settings are correct.")
    else:
        limit=st.selectbox("Records to load",[10,25,50,100,200],index=2)
        rows,err=get_recent_conversations(limit)
        if err:
            st.error("History could not be loaded. Check terminal details.")
        elif not rows:
            st.info("No saved conversations found.")
        else:
            search=st.text_input("Search records",placeholder="Type a keyword…")
            rows=[r for r in rows if search.lower() in (str(r.get("user_message",""))+" "+str(r.get("nova_response",""))).lower()]
            for r in rows:
                with st.expander(f'#{r.get("id")} · {str(r.get("user_message",""))[:65]} · {r.get("created_at","")}'):
                    st.markdown("**You**")
                    st.write(r.get("user_message",""))
                    st.markdown("**NOVA**")
                    st.write(r.get("nova_response",""))
            buf=io.StringIO()
            w=csv.DictWriter(buf,fieldnames=["id","user_message","nova_response","created_at"])
            w.writeheader()
            for r in rows:
                w.writerow({k:str(r.get(k,"")) for k in w.fieldnames})
            st.download_button("⬇ Export visible records as CSV",buf.getvalue(),"nova_conversation_history.csv","text/csv")
