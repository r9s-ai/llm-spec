"""Pipeline tests for OpenAI API - testing data flow between endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_spec.providers.openai import OpenAIClient
from tests.base import assert_report_valid


# =============================================================================
# Image Pipeline Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.expensive
class TestImagePipeline:
    """Test image generation -> edit -> variation pipeline."""

    def test_generate_then_variation(
        self,
        openai_client: OpenAIClient,
        temp_dir: Path,
        run_expensive: bool,
    ) -> None:
        """Generate an image, then create a variation of it."""
        if not run_expensive:
            pytest.skip("Use --run-expensive to run this test")

        # Step 1: Generate image
        print("\n[Step 1] Generating image...")
        image_bytes, gen_report = openai_client.generate_image(
            prompt="A simple red circle on white background",
            model="dall-e-2",
            size="256x256",
        )

        gen_report.print()
        assert_report_valid(gen_report)
        assert len(image_bytes) > 0, "Generated image should have data"

        # Save for debugging
        gen_path = temp_dir / "generated.png"
        gen_path.write_bytes(image_bytes)
        print(f"  Saved to: {gen_path} ({len(image_bytes)} bytes)")

        # Step 2: Create variation using raw bytes
        print("\n[Step 2] Creating variation from bytes...")
        var_bytes, var_report = openai_client.create_image_variation(
            image=image_bytes,
            model="dall-e-2",
            size="256x256",
        )

        var_report.print()
        assert_report_valid(var_report)
        assert len(var_bytes) > 0, "Variation should have data"

        # Save for debugging
        var_path = temp_dir / "variation.png"
        var_path.write_bytes(var_bytes)
        print(f"  Saved to: {var_path} ({len(var_bytes)} bytes)")

        print("\n[Pipeline Complete] generate -> variation")

    def test_generate_then_edit(
        self,
        openai_client: OpenAIClient,
        temp_dir: Path,
        run_expensive: bool,
    ) -> None:
        """Generate an image, then edit it."""
        if not run_expensive:
            pytest.skip("Use --run-expensive to run this test")

        # Step 1: Generate image
        print("\n[Step 1] Generating image...")
        image_bytes, gen_report = openai_client.generate_image(
            prompt="A simple white square on black background",
            model="dall-e-2",
            size="256x256",
        )

        gen_report.print()
        assert_report_valid(gen_report)

        # Save for debugging
        gen_path = temp_dir / "generated.png"
        gen_path.write_bytes(image_bytes)
        print(f"  Saved to: {gen_path} ({len(image_bytes)} bytes)")

        # Step 2: Edit the image (add something)
        print("\n[Step 2] Editing image...")
        edited_bytes, edit_report = openai_client.edit_image(
            image=image_bytes,
            prompt="Add a red circle in the center",
            model="dall-e-2",
            size="256x256",
        )

        edit_report.print()
        assert_report_valid(edit_report)
        assert len(edited_bytes) > 0, "Edited image should have data"

        # Save for debugging
        edit_path = temp_dir / "edited.png"
        edit_path.write_bytes(edited_bytes)
        print(f"  Saved to: {edit_path} ({len(edited_bytes)} bytes)")

        print("\n[Pipeline Complete] generate -> edit")

    def test_full_image_pipeline(
        self,
        openai_client: OpenAIClient,
        temp_dir: Path,
        run_expensive: bool,
    ) -> None:
        """Full pipeline: generate -> edit -> variation."""
        if not run_expensive:
            pytest.skip("Use --run-expensive to run this test")

        # Step 1: Generate
        print("\n[Step 1] Generating initial image...")
        image1, report1 = openai_client.generate_image(
            prompt="A blue square",
            model="dall-e-2",
            size="256x256",
        )
        assert_report_valid(report1)
        (temp_dir / "step1_generated.png").write_bytes(image1)
        print(f"  Generated: {len(image1)} bytes")

        # Step 2: Edit
        print("\n[Step 2] Editing image...")
        image2, report2 = openai_client.edit_image(
            image=image1,
            prompt="Add a yellow circle",
            model="dall-e-2",
            size="256x256",
        )
        assert_report_valid(report2)
        (temp_dir / "step2_edited.png").write_bytes(image2)
        print(f"  Edited: {len(image2)} bytes")

        # Step 3: Variation
        print("\n[Step 3] Creating variation...")
        image3, report3 = openai_client.create_image_variation(
            image=image2,
            model="dall-e-2",
            size="256x256",
        )
        assert_report_valid(report3)
        (temp_dir / "step3_variation.png").write_bytes(image3)
        print(f"  Variation: {len(image3)} bytes")

        print(f"\n[Pipeline Complete] All artifacts saved to: {temp_dir}")


# =============================================================================
# Audio Pipeline Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.expensive
class TestAudioPipeline:
    """Test speech generation -> transcription pipeline."""

    def test_speech_then_transcription(
        self,
        openai_client: OpenAIClient,
        temp_dir: Path,
        run_expensive: bool,
    ) -> None:
        """Generate speech, then transcribe it back to text."""
        if not run_expensive:
            pytest.skip("Use --run-expensive to run this test")

        original_text = "Hello, this is a test of the speech to text pipeline."

        # Step 1: Generate speech
        print(f"\n[Step 1] Generating speech for: '{original_text}'")
        audio_bytes = openai_client.generate_speech(
            input_text=original_text,
            model="tts-1",
            voice="alloy",
            response_format="mp3",
        )

        assert len(audio_bytes) > 0, "Audio should have data"

        # Save for debugging
        audio_path = temp_dir / "speech.mp3"
        audio_path.write_bytes(audio_bytes)
        print(f"  Saved to: {audio_path} ({len(audio_bytes)} bytes)")

        # Step 2: Transcribe back
        print("\n[Step 2] Transcribing audio...")
        response, report = openai_client.transcribe_audio(
            audio=audio_bytes,
            model="whisper-1",
            response_format="json",
        )

        report.print()
        assert_report_valid(report)

        transcribed_text = response.get("text", "")
        print(f"  Original:    '{original_text}'")
        print(f"  Transcribed: '{transcribed_text}'")

        # Basic check that transcription captured something
        assert len(transcribed_text) > 0, "Transcription should return text"

        print("\n[Pipeline Complete] speech -> transcription")

    def test_speech_then_verbose_transcription(
        self,
        openai_client: OpenAIClient,
        temp_dir: Path,
        run_expensive: bool,
    ) -> None:
        """Generate speech, then transcribe with verbose output."""
        if not run_expensive:
            pytest.skip("Use --run-expensive to run this test")

        original_text = "Testing verbose transcription with timestamps."

        # Step 1: Generate speech
        print(f"\n[Step 1] Generating speech for: '{original_text}'")
        audio_bytes = openai_client.generate_speech(
            input_text=original_text,
            model="tts-1",
            voice="nova",
            response_format="mp3",
        )

        audio_path = temp_dir / "speech_verbose.mp3"
        audio_path.write_bytes(audio_bytes)
        print(f"  Saved to: {audio_path}")

        # Step 2: Transcribe with verbose format
        print("\n[Step 2] Transcribing with verbose_json format...")
        response, report = openai_client.transcribe_audio(
            audio=audio_bytes,
            model="whisper-1",
            response_format="verbose_json",
        )

        report.print()
        assert_report_valid(report)

        # Check verbose fields
        assert "text" in response, "Should have text field"
        assert "language" in response, "Should have language field"

        print(f"  Language: {response.get('language')}")
        print(f"  Duration: {response.get('duration')} seconds")
        print(f"  Text: {response.get('text')}")

        print("\n[Pipeline Complete] speech -> verbose transcription")

    @pytest.mark.parametrize("voice", ["alloy", "echo", "nova"])
    def test_multiple_voices_pipeline(
        self,
        openai_client: OpenAIClient,
        temp_dir: Path,
        run_expensive: bool,
        voice: str,
    ) -> None:
        """Test speech->transcription pipeline with different voices."""
        if not run_expensive:
            pytest.skip("Use --run-expensive to run this test")

        text = "Testing different voice synthesis."

        # Generate speech
        audio_bytes = openai_client.generate_speech(
            input_text=text,
            model="tts-1",
            voice=voice,
        )

        audio_path = temp_dir / f"speech_{voice}.mp3"
        audio_path.write_bytes(audio_bytes)

        # Transcribe
        response, report = openai_client.transcribe_audio(audio=audio_bytes)

        assert_report_valid(report)
        print(f"  Voice '{voice}': {response.get('text', '')[:50]}...")
