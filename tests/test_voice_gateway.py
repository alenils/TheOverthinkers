"""Unit tests for voice gateway, Gemini 3.8 STT, and WhatsApp channel integration."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent

import e2e_whatsapp_demo
import gemini_stt
import messaging_gateway


class TestVoiceGateway(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_gemini_stt_transcription(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "I have a launch deadline today and feel stressed."
        mock_client.models.generate_content.return_value = mock_response

        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_types = MagicMock()

        input_audio = Path(self.temp_dir) / "test_audio.wav"
        input_audio.write_bytes(b"RIFFdummywavdata")
        output_dir = Path(self.temp_dir) / "output"

        with patch.object(gemini_stt, "_HAS_GENAI", True), \
             patch.object(gemini_stt, "genai", mock_genai), \
             patch.object(gemini_stt, "types", mock_types):
            transcript = gemini_stt.transcribe(input_audio, output_dir)

        self.assertEqual(transcript, "I have a launch deadline today and feel stressed.")

        out_txt = output_dir / "test_audio.txt"
        self.assertTrue(out_txt.is_file())
        self.assertEqual(out_txt.read_text(encoding="utf-8"), transcript)

    @patch("subprocess.run")
    def test_whatsapp_dispatcher_execution(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock(returncode=0)
        spool_dir = Path(self.temp_dir) / "spool"
        dispatcher = messaging_gateway.ChannelDispatcher(
            channel="whatsapp",
            spool_dir=spool_dir,
            recipient="37000000000",
        )

        event = dispatcher.dispatch("Morning check-in test", is_simulated=True)
        self.assertTrue(event.is_simulated)
        self.assertIn("[Simulated Alert]", event.text)
        self.assertEqual(event.channel, "whatsapp")

        # Verify hermes send was called
        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0][0]
        self.assertEqual(args[0], "hermes")
        self.assertEqual(args[1], "send")
        self.assertEqual(args[2], "--to")
        self.assertEqual(args[3], "whatsapp:37000000000")

    @patch("e2e_whatsapp_demo.send_whatsapp_checkin")
    @patch("e2e_whatsapp_demo.check_pairing_status")
    def test_e2e_whatsapp_demo_flow(self, mock_pairing, mock_send):
        mock_pairing.return_value = True
        mock_send.return_value = True

        ledger_db = Path(self.temp_dir) / "test_ledger.db"
        result = e2e_whatsapp_demo.run_e2e_demo("37000000000", ledger_db=ledger_db)

        self.assertEqual(result["status"], "DISPATCHED")
        self.assertEqual(result["recipient"], "37000000000")
        self.assertIn("session_id", result)
        self.assertEqual(result["entry_id"], 1)


if __name__ == "__main__":
    unittest.main()
