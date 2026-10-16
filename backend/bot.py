import io
import os
import requests
from dotenv import load_dotenv

from pipecat.utils.text.markdown_text_filter import MarkdownTextFilter
from pipecat.processors.aggregators.sentence import SentenceAggregator
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.processors.audio.vad_processor import VADProcessor
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.serializers.base_serializer import FrameSerializer
from pipecat.frames.frames import Frame, InputAudioRawFrame, OutputAudioRawFrame

load_dotenv()

class RawPCMFrameSerializer(FrameSerializer):
    def __init__(self, sample_rate: int = 16000, num_channels: int = 1):
        super().__init__()
        self.sample_rate = sample_rate
        self.num_channels = num_channels

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, OutputAudioRawFrame):
            return frame.audio
        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if isinstance(data, bytes):
            return InputAudioRawFrame(
                audio=data,
                sample_rate=self.sample_rate,
                num_channels=self.num_channels
            )
        return None


# Lazy-initialize STT model
_stt = None

def get_stt():
    global _stt
    if _stt is None:
        _stt = WhisperSTTService(settings=WhisperSTTService.Settings(model="tiny"))
    return _stt

async def run_voice_agent(transport, chat_history: list = None):
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")

    # Initialize LLM with automatic working key selection
    if gemini_key and gemini_key.startswith("AIzaSy"):
        from pipecat.services.google.llm import GoogleLLMService, GoogleLLMSettings
        llm = GoogleLLMService(
            api_key=gemini_key,
            settings=GoogleLLMSettings(model="gemini-1.5-flash")
        )
    else:
        from pipecat.services.openai.llm import OpenAILLMService
        llm = OpenAILLMService(
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
            settings=OpenAILLMService.Settings(model="openai/gpt-4o-mini")
        )

    # 2. Resilient Neural Voice Synthesis (Local Kokoro Engine)
    tts = KokoroTTSService(
        voice_id="af_heart",
        sample_rate=16000
    )
    
    # Attach the Markdown text filter directly to the TTS engine
    markdown_filter = MarkdownTextFilter()
    tts.add_text_filter(markdown_filter)

    # Configure VAD to detect end-of-speech faster (0.4s pause instead of ~1s)
    vad_analyzer = SileroVADAnalyzer(params=VADParams(stop_secs=0.4))
    vad_processor = VADProcessor(vad_analyzer=vad_analyzer)

    # 3. Build memory context combining System Prompt + Previous Chat History
    base_messages = [{
        "role": "system",
        "content": (
            "You are Aanandi, the client-facing AI Sales Engineer for Aanandi TechnoSoft LLP (https://aanandi.in). "
            "You are speaking with a prospective client on a live voice call, transitioning from website text chat. "
            "Aanandi TechnoSoft is an elite AI-Powered Product Engineering and Workflow Automation Partner with 15+ years of experience, "
            "500+ delivered platforms, and 9 live commercial apps (Uclean Laundry, Swagmee Fashion, Jotno Patient Healthcare EHR, HungerGo, Careasy, etc.). "
            "STRICT RULES: "
            "1. You pitch ONLY Aanandi's client services, workflow automations, SaaS platforms, and portfolio. You are EXPLICITLY FORBIDDEN from discussing your own underlying source code or internal stack (do NOT mention LangGraph, Pipecat, FastAPI, WebSockets, or WebRTC). "
            "2. Review the chat history carefully, greet them by name if known, and acknowledge any requirements they already shared. "
            "3. Keep answers conversational, consultative, and brief (1-2 spoken sentences). "
            "4. Do not use any markdown formatting (no asterisks, no bullet points). "
            "5. Explicitly ask the user what business workflow or software platform they want to build. "
            "6. DO NOT ask to book a calendar slot during the call, as they are speaking with you directly. When concluding, explain they can connect with our senior technical leadership team."
        )
    }]

    # Inject history from text chat session if available
    if chat_history:
        base_messages.extend(chat_history)
    else:
        base_messages.append({"role": "assistant", "content": "Hello! I'm Aanandi. How can I help you with your project today?"})

    context = LLMContext(messages=base_messages)
    context_aggregator = LLMContextAggregatorPair(context)

    # Initialize the sentence aggregator
    sentence_aggregator = SentenceAggregator()

    # Add components into the Pipeline list (Markdown filter is removed from here)
    stt_instance = get_stt()
    pipeline = Pipeline([
        transport.input(),
        vad_processor,
        stt_instance,
        context_aggregator.user(),
        llm,
        sentence_aggregator,
        tts,
        transport.output(),
        context_aggregator.assistant()
    ])

    task = PipelineTask(pipeline, params=PipelineParams())
    runner = PipelineRunner()
    await runner.run(task)