import Axios from "axios";
import * as React from "react";
import {
    Component,
    ComponentMeta,
    ComponentProps,
    PComponent,
    PropertyTree,
    SizeObject
} from "@inductiveautomation/perspective-client";
import { bind } from "bind-decorator";

export const COMPONENT_TYPE = "rad.display.ragChat";

// --- Icons (SVG) - Updated to Generic AI & Larger Size ---

const IconAI = () => (
    // Robot/Bot Icon
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#5f6368" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="11" width="18" height="10" rx="2" />
        <circle cx="12" cy="5" r="2" />
        <path d="M12 7v4" />
        <line x1="8" y1="16" x2="8" y2="16" />
        <line x1="16" y1="16" x2="16" y2="16" />
    </svg>
);

const IconUser = () => (
    // User Icon - Slightly larger to match
    <svg width="28" height="28" viewBox="0 0 24 24" fill="#5f6368" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 12C14.21 12 16 10.21 16 8C16 5.79 14.21 4 12 4C9.79 4 8 5.79 8 8C8 10.21 9.79 12 12 12ZM12 14C9.33 14 4 15.34 4 18V20H20V18C20 15.34 14.67 14 12 14Z" />
    </svg>
);

const IconSend = () => (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M2.01 21L23 12L2.01 3L2 10L17 12L2 14L2.01 21Z" fill="currentColor" />
    </svg>
);

// --- Interfaces ---
interface RagChatProps {
    title: string;
    maxResults: number;
    endpointUrl: string;
    headerBackground: string;
    headerTextColor: string;
    containerBackground: string;
    messageBackgroundUser: string;
    messageTextColorUser: string;
    messageBackgroundAssistant: string;
    messageTextColorAssistant: string;
    inputBackground: string;
    inputTextColor: string;
}

interface RagChatSource {
    file: string;
    score: number;
    snippet: string;
}

interface RagChatResponse {
    answer: string;
    sources?: RagChatSource[];
}

interface RagChatMessage {
    role: "user" | "assistant" | "system";
    text: string;
    sources?: RagChatSource[];
}

interface RagChatState {
    input: string;
    busy: boolean;
    messages: RagChatMessage[];
    configError?: string;
}

// --- CSS Styles ---
const STYLES = `
    .rag-chat-component {
        width: 100%;
        height: 100%;
        min-height: 0;
        min-width: 0;
    }
    .rag-chat-container {
        display: flex;
        flex-direction: column;
        min-height: 0;
        height: 100%;
        width: 100%;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background-color: var(--rag-container-bg, #ffffff);
        color: #1f1f1f;
        border-radius: 8px;
        overflow: hidden;
    }
    .rag-header {
        padding: 16px 20px;
        font-size: 18px; /* Slightly larger header text */
        font-weight: 600;
        border-bottom: 1px solid #e0e0e0;
        background: var(--rag-header-bg, #ffffff);
        color: var(--rag-header-text, #202124);
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .rag-messages-area {
        flex: 1 1 auto;
        min-height: 0;
        overflow-y: auto;
        padding: 20px;
        display: flex;
        flex-direction: column;
        gap: 24px;
        background-color: var(--rag-container-bg, #ffffff);
    }
    .message-row {
        display: flex;
        gap: 12px;
        max-width: 100%;
        align-items: flex-start;
    }
    .message-row.user {
        justify-content: flex-end;
    }
    .message-row.assistant {
        justify-content: flex-start;
    }
    /* Avatar Column Width Increased for larger icons */
    .avatar-col {
        width: 44px; 
        display: flex;
        justify-content: center;
        padding-top: 2px;
        flex-shrink: 0;
    }
    .avatar-circle {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background-color: #f1f3f4;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .message-content {
        max-width: 80%;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .bubble {
        padding: 14px 20px;
        border-radius: 18px;
        font-size: 15px;
        line-height: 1.6;
        white-space: pre-wrap;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .message-row.user .bubble {
        background-color: var(--rag-user-bg, #0b57d0);
        color: var(--rag-user-text, #ffffff);
        border-bottom-right-radius: 4px;
    }
    .message-row.assistant .bubble {
        background-color: var(--rag-assistant-bg, #f1f3f4);
        color: var(--rag-assistant-text, #1f1f1f);
        border-bottom-left-radius: 4px;
    }
    .system-message {
        text-align: center;
        font-size: 13px;
        color: #757575;
        margin: 10px 0;
        background: #f8f9fa;
        padding: 4px 12px;
        border-radius: 12px;
        align-self: center;
    }
    .sources-list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 4px;
    }
    .source-chip {
        font-size: 12px;
        background: #fff;
        border: 1px solid #dadce0;
        border-radius: 8px;
        padding: 6px 10px;
        color: #5f6368;
        cursor: help;
        transition: all 0.2s;
    }
    .source-chip:hover {
        background: #f1f3f4;
        border-color: #202124;
    }
    .input-area {
        padding: 16px 20px;
        background: var(--rag-container-bg, #ffffff);
        border-top: 1px solid #f0f0f0;
        flex: 0 0 auto;
    }
    .input-wrapper {
        display: flex;
        align-items: center;
        background: var(--rag-input-bg, #f1f3f4);
        border-radius: 28px;
        padding: 8px 8px 8px 24px;
        transition: background 0.2s;
    }
    .input-wrapper:focus-within {
        background: #e8eaed;
        box-shadow: 0 0 0 1px #dadce0;
    }
    .chat-input {
        flex: 1;
        border: none;
        background: transparent;
        font-size: 15px;
        outline: none;
        color: var(--rag-input-text, #202124);
        padding: 8px 0;
    }
    .send-btn {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        border: none;
        background: transparent;
        color: #5f6368;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
    }
    .send-btn:hover:not(:disabled) {
        background: #dadce0;
        color: #0b57d0;
    }
    .send-btn:disabled {
        opacity: 0.4;
        cursor: not-allowed;
    }
    .error-banner {
        background: #fce8e6;
        color: #c5221f;
        padding: 8px 12px;
        font-size: 13px;
        text-align: center;
        border-bottom: 1px solid #fad2cf;
    }
    .typing-indicator span {
        display: inline-block;
        width: 6px;
        height: 6px;
        background-color: #80868b;
        border-radius: 50%;
        animation: typing 1.4s infinite ease-in-out both;
        margin: 0 2px;
    }
    .typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
    .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
    @keyframes typing {
        0%, 80%, 100% { transform: scale(0); }
        40% { transform: scale(1); }
    }
`;

export class RagChatComponent extends Component<ComponentProps<RagChatProps>, RagChatState> {
    state: RagChatState = {
        input: "",
        busy: false,
        messages: [
            {
                role: "system",
                text: "RAG Assistant connected."
            }
        ]
    };

    private messagesEndRef: React.RefObject<HTMLDivElement>;

    constructor(props: ComponentProps<RagChatProps>) {
        super(props);
        this.messagesEndRef = React.createRef();
    }

    componentDidMount(): void {
        this.scrollToBottom();
    }

    componentDidUpdate(prevProps: ComponentProps<RagChatProps>, prevState: RagChatState) {
        if (prevState.messages.length !== this.state.messages.length) {
            this.scrollToBottom();
        }
    }

    private scrollToBottom() {
        this.messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }


    @bind
    onInputChange(event: React.ChangeEvent<HTMLInputElement>) {
        this.setState({ input: event.target.value });
    }

    @bind
    async sendMessage() {
        const message = this.state.input.trim();
        if (!message || this.state.busy) return;

        const endpointUrl = this.getEndpointUrl();
        if (!endpointUrl) {
            this.setState((prev) => ({
                messages: [...prev.messages, { role: "assistant", text: "Error: Endpoint URL not configured." }]
            }));
            return;
        }

        this.setState((prev) => ({
            input: "",
            busy: true,
            messages: [...prev.messages, { role: "user", text: message }]
        }));

        try {
            const response = await Axios.post<RagChatResponse>(endpointUrl, {
                question: message,
                maxResults: this.props.props.maxResults
            });

            const answer = response.data?.answer ?? "No response received.";
            const sources = response.data?.sources ?? [];
            this.setState((prev) => ({
                busy: false,
                messages: [...prev.messages, { role: "assistant", text: answer, sources }]
            }));
        } catch (err: any) {
            this.setState((prev) => ({
                busy: false,
                messages: [...prev.messages, { role: "assistant", text: `Error: ${err?.message ?? err}` }]
            }));
        }
    }

    private getEndpointUrl(): string | undefined {
        const raw = this.props.props.endpointUrl?.trim();
        if (!raw) return undefined;
        if (raw.includes("://")) return raw;
        return `http://${raw}`;
    }

    renderSources(sources?: RagChatSource[]) {
        if (!sources || sources.length === 0) return null;
        return (
            <div className="sources-list">
                {sources.map((s, i) => (
                    <div key={i} className="source-chip" title={`${s.file} (Score: ${s.score.toFixed(2)})`}>
                        📄 {s.file}
                    </div>
                ))}
            </div>
        );
    }

    render() {
        // Here we read the title from the props passed by the Designer
        const {
            title,
            headerBackground,
            headerTextColor,
            containerBackground,
            messageBackgroundUser,
            messageTextColorUser,
            messageBackgroundAssistant,
            messageTextColorAssistant,
            inputBackground,
            inputTextColor
        } = this.props.props;
        const styleVars: React.CSSProperties = {
            ["--rag-header-bg" as any]: headerBackground,
            ["--rag-header-text" as any]: headerTextColor,
            ["--rag-container-bg" as any]: containerBackground,
            ["--rag-user-bg" as any]: messageBackgroundUser,
            ["--rag-user-text" as any]: messageTextColorUser,
            ["--rag-assistant-bg" as any]: messageBackgroundAssistant,
            ["--rag-assistant-text" as any]: messageTextColorAssistant,
            ["--rag-input-bg" as any]: inputBackground,
            ["--rag-input-text" as any]: inputTextColor
        };

        const emitProps = this.props.emit({ classes: ["rag-chat-component"] });
        const mergedStyle = {
            ...(emitProps.style as React.CSSProperties),
            ...styleVars
        };

        return (
            <div {...emitProps} style={mergedStyle}>
                <style>{STYLES}</style>
                
                <div className="rag-chat-container">
                    <div className="rag-header">
                        <IconAI /> {title}
                    </div>

                    {this.state.configError && (
                        <div className="error-banner">{this.state.configError}</div>
                    )}

                    <div className="rag-messages-area">
                        {this.state.messages.map((m, idx) => {
                            if (m.role === 'system') {
                                return <div key={idx} className="system-message">{m.text}</div>;
                            }
                            
                            const isUser = m.role === 'user';
                            return (
                                <div key={idx} className={`message-row ${m.role}`}>
                                    {!isUser && (
                                        <div className="avatar-col">
                                            <div className="avatar-circle">
                                                <IconAI />
                                            </div> 
                                        </div>
                                    )}
                                    
                                    <div className="message-content">
                                        <div className="bubble">
                                            {m.text}
                                        </div>
                                        {!isUser && this.renderSources(m.sources)}
                                    </div>

                                    {isUser && (
                                        <div className="avatar-col">
                                           <div className="avatar-circle">
                                                <IconUser />
                                           </div>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                        {this.state.busy && (
                            <div className="message-row assistant">
                                <div className="avatar-col">
                                    <div className="avatar-circle">
                                        <IconAI />
                                    </div>
                                </div>
                                <div className="bubble typing-indicator">
                                    <span></span><span></span><span></span>
                                </div>
                            </div>
                        )}
                        <div ref={this.messagesEndRef} />
                    </div>

                    <div className="input-area">
                        <div className="input-wrapper">
                            <input
                                type="text"
                                className="chat-input"
                                value={this.state.input}
                                onChange={this.onInputChange}
                                placeholder="Ask a question..."
                                onKeyDown={(e) => (e.key === "Enter" ? this.sendMessage() : null)}
                                disabled={this.state.busy}
                            />
                            <button className="send-btn" onClick={this.sendMessage} disabled={this.state.busy || !this.state.input.trim()}>
                                <IconSend />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }
}

export class RagChatMeta implements ComponentMeta {
    getComponentType(): string {
        return COMPONENT_TYPE;
    }

    getDefaultSize(): SizeObject {
        return { width: 450, height: 600 };
    }

    // --------------------------------------------------------
    // This connects the 'title' prop to the Designer property tree
    // --------------------------------------------------------
    getPropsReducer(tree: PropertyTree): RagChatProps {
        return {
            title: tree.readString("title", "AI Assistant"),
            maxResults: tree.readNumber("maxResults", 3),
            endpointUrl: tree.readString("endpointUrl", ""),
            headerBackground: tree.readString("headerBackground", "#ffffff"),
            headerTextColor: tree.readString("headerTextColor", "#202124"),
            containerBackground: tree.readString("containerBackground", "#ffffff"),
            messageBackgroundUser: tree.readString("messageBackgroundUser", "#0b57d0"),
            messageTextColorUser: tree.readString("messageTextColorUser", "#ffffff"),
            messageBackgroundAssistant: tree.readString("messageBackgroundAssistant", "#f1f3f4"),
            messageTextColorAssistant: tree.readString("messageTextColorAssistant", "#1f1f1f"),
            inputBackground: tree.readString("inputBackground", "#f1f3f4"),
            inputTextColor: tree.readString("inputTextColor", "#202124")
        };
    }

    getViewComponent(): PComponent {
        return RagChatComponent;
    }
}
