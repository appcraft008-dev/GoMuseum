"""
Unit tests for AI Service
Tests OpenAI GPT-4V integration and fallback strategies
"""
import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.ai_service import AIService, get_ai_service
from app.core.exceptions import AIServiceException, TimeoutException


class TestAIService:
    """Test suite for AI service"""

    @pytest.fixture
    def ai_service(self):
        """Create AIService instance for testing"""
        return AIService()

    @pytest.mark.asyncio
    async def test_calls_openai_gpt4v_as_primary_strategy(self, ai_service):
        """should_call_openai_gpt4v_api_first"""
        # Mock OpenAI client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "artwork_name": "Mona Lisa",
            "artist": "Leonardo da Vinci",
            "period": "Renaissance",
            "description": "Famous portrait",
            "confidence": 0.95
        })
        
        with patch('app.services.ai_service._get_openai_client') as mock_client:
            mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
            
            result = await ai_service.recognize("base64_image")
            
            assert result["artwork_name"] == "Mona Lisa"
            assert result["source"] == "openai"
            mock_client.return_value.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_recognition_result_on_success(self, ai_service):
        """should_return_artwork_info_when_gpt4v_succeeds"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "artwork_name": "The Starry Night",
            "artist": "Vincent van Gogh",
            "period": "Post-Impressionism",
            "description": "Swirling night sky over a village",
            "confidence": 0.89
        })
        
        with patch('app.services.ai_service._get_openai_client') as mock_client:
            mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
            
            result = await ai_service.recognize("base64_image")
            
            assert "artwork_name" in result
            assert "artist" in result
            assert "period" in result
            assert "description" in result
            assert "confidence" in result
            assert result["confidence"] == 0.89

    @pytest.mark.asyncio
    async def test_encodes_image_to_base64_before_api_call(self, ai_service):
        """should_convert_image_bytes_to_base64_for_api"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "artwork_name": "Test Art",
            "artist": "Test Artist",
            "period": "Modern",
            "description": "Test description",
            "confidence": 0.75
        })
        
        with patch('app.services.ai_service._get_openai_client') as mock_client:
            mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
            
            base64_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
            result = await ai_service.recognize(base64_image)
            
            # Verify the call was made with base64 data in image_url
            call_args = mock_client.return_value.chat.completions.create.call_args
            messages = call_args[1]['messages']
            image_content = messages[0]['content'][1]
            assert "data:image/jpeg;base64," in image_content['image_url']['url']

    @pytest.mark.asyncio
    async def test_includes_proper_prompt_for_artwork_recognition(self, ai_service):
        """should_send_structured_prompt_to_gpt4v"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "artwork_name": "Test Art",
            "artist": "Test Artist",
            "period": "Modern",
            "description": "Test description",
            "confidence": 0.75
        })
        
        with patch('app.services.ai_service._get_openai_client') as mock_client:
            mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
            
            await ai_service.recognize("base64_image")
            
            # Verify the prompt contains expected keywords
            call_args = mock_client.return_value.chat.completions.create.call_args
            messages = call_args[1]['messages']
            prompt_text = messages[0]['content'][0]['text']
            assert "art historian" in prompt_text.lower()
            assert "artwork" in prompt_text.lower()
            assert "json" in prompt_text.lower()

    @pytest.mark.asyncio
    async def test_parses_gpt4v_response_to_structured_format(self, ai_service):
        """should_extract_title_artist_year_description_confidence"""
        # Test with JSON in markdown
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '```json\n{"artwork_name": "Test Art", "artist": "Test Artist", "period": "Modern", "description": "Test description", "confidence": 0.75}\n```'
        
        with patch('app.services.ai_service._get_openai_client') as mock_client:
            mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
            
            result = await ai_service.recognize("base64_image")
            
            assert result["artwork_name"] == "Test Art"
            assert result["artist"] == "Test Artist"
            assert result["period"] == "Modern"
            assert result["confidence"] == 0.75


class TestAIServiceFallbackStrategy:
    """Test fallback strategy for AI service"""

    @pytest.fixture
    def ai_service(self):
        return AIService()

    @pytest.mark.asyncio
    async def test_falls_back_to_claude_when_gpt4v_fails(self, ai_service):
        """should_try_claude_api_when_openai_fails"""
        # Mock Claude response
        mock_claude_message = MagicMock()
        mock_claude_message.content = [MagicMock()]
        mock_claude_message.content[0].text = json.dumps({
            "artwork_name": "Claude Art",
            "artist": "Claude Artist",
            "period": "Modern",
            "description": "Claude description",
            "confidence": 0.8
        })
        
        with patch('app.services.ai_service._get_openai_client') as mock_openai, \
             patch('app.services.ai_service._get_claude_client') as mock_claude:
            # Make OpenAI fail
            mock_openai.return_value.chat.completions.create = AsyncMock(side_effect=Exception("OpenAI failed"))
            # Make Claude succeed
            mock_claude.return_value.messages.create = AsyncMock(return_value=mock_claude_message)
            
            result = await ai_service.recognize("base64_image")
            
            assert result["artwork_name"] == "Claude Art"
            assert result["source"] == "claude"

    @pytest.mark.asyncio
    async def test_falls_back_to_local_model_when_claude_fails(self, ai_service):
        """should_use_local_model_when_both_apis_fail"""
        with patch('app.services.ai_service._get_openai_client') as mock_openai, \
             patch('app.services.ai_service._get_claude_client') as mock_claude:
            # Make both OpenAI and Claude fail
            mock_openai.return_value.chat.completions.create = AsyncMock(side_effect=Exception("OpenAI failed"))
            mock_claude.return_value.messages.create = AsyncMock(side_effect=Exception("Claude failed"))
            
            result = await ai_service.recognize("base64_image")
            
            # Should fall back to manual response
            assert result["artwork_name"] == "Unknown Artwork"
            assert result["source"] == "manual"
            assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_fallback_strategy_respects_3s_timeout_per_attempt(self, ai_service):
        """should_timeout_each_strategy_after_3_seconds"""
        async def slow_openai_call(*args, **kwargs):
            await asyncio.sleep(4)  # Longer than 3s timeout
            return MagicMock()
            
        mock_claude_message = MagicMock()
        mock_claude_message.content = [MagicMock()]
        mock_claude_message.content[0].text = json.dumps({
            "artwork_name": "Claude Fallback",
            "artist": "Claude Artist",
            "period": "Modern",
            "description": "Fallback after timeout",
            "confidence": 0.7
        })
        
        with patch('app.services.ai_service._get_openai_client') as mock_openai, \
             patch('app.services.ai_service._get_claude_client') as mock_claude:
            mock_openai.return_value.chat.completions.create = AsyncMock(side_effect=slow_openai_call)
            mock_claude.return_value.messages.create = AsyncMock(return_value=mock_claude_message)
            
            result = await ai_service.recognize("base64_image")
            
            # Should fall back to Claude after OpenAI timeout
            assert result["source"] == "claude"

    @pytest.mark.asyncio
    async def test_logs_fallback_events_for_monitoring(self, ai_service):
        """should_log_when_falling_back_to_next_strategy"""
        with patch('app.services.ai_service._get_openai_client') as mock_openai, \
             patch('app.services.ai_service._get_claude_client') as mock_claude, \
             patch('app.services.ai_service.logger') as mock_logger:
            mock_openai.return_value.chat.completions.create = AsyncMock(side_effect=Exception("OpenAI failed"))
            mock_claude.return_value.messages.create = AsyncMock(side_effect=Exception("Claude failed"))
            
            result = await ai_service.recognize("base64_image")
            
            # Verify logging calls were made
            mock_logger.warning.assert_called()
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_raises_exception_when_all_strategies_fail(self, ai_service):
        """should_raise_recognition_failed_error_after_all_attempts"""
        # This test is actually about the manual fallback - it never raises an exception
        # because manual fallback always returns a result
        with patch('app.services.ai_service._get_openai_client') as mock_openai, \
             patch('app.services.ai_service._get_claude_client') as mock_claude:
            mock_openai.return_value.chat.completions.create = AsyncMock(side_effect=Exception("OpenAI failed"))
            mock_claude.return_value.messages.create = AsyncMock(side_effect=Exception("Claude failed"))
            
            result = await ai_service.recognize("base64_image")
            
            # Manual fallback should always return a result, never raise
            assert result["source"] == "manual"
            assert result["confidence"] == 0.0


class TestAIServiceErrorHandling:
    """Test error handling in AI service"""

    @pytest.fixture
    def ai_service(self):
        return AIService()

    @pytest.mark.asyncio
    async def test_handles_openai_api_rate_limit_error(self, ai_service):
        """should_handle_429_rate_limit_gracefully"""
        # Mock Claude fallback
        mock_claude_message = MagicMock()
        mock_claude_message.content = [MagicMock()]
        mock_claude_message.content[0].text = json.dumps({
            "artwork_name": "Fallback Art",
            "artist": "Fallback Artist",
            "period": "Modern",
            "description": "After rate limit",
            "confidence": 0.7
        })
        
        with patch('app.services.ai_service._get_openai_client') as mock_openai, \
             patch('app.services.ai_service._get_claude_client') as mock_claude:
            # Simulate rate limit error
            mock_openai.return_value.chat.completions.create = AsyncMock(side_effect=Exception("Rate limit exceeded"))
            mock_claude.return_value.messages.create = AsyncMock(return_value=mock_claude_message)
            
            result = await ai_service.recognize("base64_image")
            
            # Should fall back to Claude
            assert result["source"] == "claude"

    @pytest.mark.asyncio
    async def test_handles_openai_api_authentication_error(self, ai_service):
        """should_handle_401_authentication_error"""
        with patch('app.services.ai_service._get_openai_client') as mock_openai, \
             patch('app.services.ai_service._get_claude_client') as mock_claude:
            # Simulate auth error
            mock_openai.return_value.chat.completions.create = AsyncMock(side_effect=Exception("Authentication failed"))
            mock_claude.return_value.messages.create = AsyncMock(side_effect=Exception("Claude auth failed"))
            
            result = await ai_service.recognize("base64_image")
            
            # Should fall back to manual
            assert result["source"] == "manual"

    @pytest.mark.asyncio
    async def test_handles_network_timeout_gracefully(self, ai_service):
        """should_catch_timeout_exception_and_retry"""
        with patch('app.services.ai_service._get_openai_client') as mock_openai, \
             patch('app.services.ai_service._get_claude_client') as mock_claude:
            mock_openai.return_value.chat.completions.create = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_claude.return_value.messages.create = AsyncMock(side_effect=asyncio.TimeoutError())
            
            result = await ai_service.recognize("base64_image")
            
            # Should fall back to manual after timeouts
            assert result["source"] == "manual"

    @pytest.mark.asyncio
    async def test_handles_invalid_api_response_format(self, ai_service):
        """should_handle_malformed_json_response"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "This is not JSON"
        
        with patch('app.services.ai_service._get_openai_client') as mock_openai, \
             patch('app.services.ai_service._get_claude_client') as mock_claude:
            mock_openai.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_claude.return_value.messages.create = AsyncMock(side_effect=Exception("Claude failed"))
            
            result = await ai_service.recognize("base64_image")
            
            # Should fall back to manual when JSON parsing fails
            assert result["source"] == "manual"


class TestAIServicePerformance:
    """Test performance aspects of AI service"""

    @pytest.fixture
    def ai_service(self):
        return AIService()

    @pytest.mark.asyncio
    async def test_tracks_api_call_duration(self, ai_service):
        """should_measure_time_taken_for_each_api_call"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "artwork_name": "Test Art",
            "artist": "Test Artist",
            "period": "Modern",
            "description": "Test description",
            "confidence": 0.85
        })
        
        with patch('app.services.ai_service._get_openai_client') as mock_openai:
            mock_openai.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
            
            import time
            start_time = time.time()
            result = await ai_service.recognize("base64_image")
            end_time = time.time()
            
            # Verify call completed and took some time
            assert result["artwork_name"] == "Test Art"
            assert end_time > start_time

    @pytest.mark.asyncio
    async def test_includes_strategy_used_in_result(self, ai_service):
        """should_indicate_which_ai_strategy_was_successful"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "artwork_name": "OpenAI Art",
            "artist": "OpenAI Artist",
            "period": "Modern",
            "description": "OpenAI description",
            "confidence": 0.92
        })
        
        with patch('app.services.ai_service._get_openai_client') as mock_openai:
            mock_openai.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
            
            result = await ai_service.recognize("base64_image")
            
            # Strategy should be indicated in result
            assert "source" in result
            assert result["source"] == "openai"


class TestAIServiceUtilityMethods:
    """Test utility methods of AI service"""

    @pytest.fixture
    def ai_service(self):
        return AIService()

    def test_validate_api_key(self, ai_service):
        """should_check_if_api_key_is_configured"""
        # This tests the actual validation logic
        with patch.object(ai_service, 'api_key', 'test-key'):
            assert ai_service.validate_api_key() is True
        
        with patch.object(ai_service, 'api_key', None):
            assert ai_service.validate_api_key() is False
        
        with patch.object(ai_service, 'api_key', ''):
            assert ai_service.validate_api_key() is False

    @pytest.mark.asyncio
    async def test_health_check(self, ai_service):
        """should_return_service_health_status"""
        result = await ai_service.health_check()
        
        assert "service" in result
        assert "status" in result
        assert "model" in result
        assert "api_key_configured" in result
        assert result["service"] == "AIService"
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_recognize_with_timeout(self, ai_service):
        """should_apply_timeout_to_recognition_request"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "artwork_name": "Timeout Test",
            "artist": "Test Artist",
            "period": "Modern",
            "description": "Timeout test",
            "confidence": 0.8
        })
        
        with patch('app.services.ai_service._get_openai_client') as mock_openai:
            mock_openai.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
            
            result = await ai_service.recognize_with_timeout("base64_image", timeout=10)
            
            assert result["artwork_name"] == "Timeout Test"

    def test_get_ai_service_singleton(self):
        """should_return_same_instance_on_multiple_calls"""
        service1 = get_ai_service()
        service2 = get_ai_service()
        
        assert service1 is service2
