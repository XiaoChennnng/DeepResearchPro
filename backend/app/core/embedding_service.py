"""
向量嵌入服务
负责生成文本的向量表示，支持多种后端
"""

from typing import List, Optional
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings
from app.core.logging import logger

class EmbeddingService:
    """嵌入服务单例"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_service()
        return cls._instance
    
    def _init_service(self):
        """初始化嵌入模型"""
        self.embeddings = None
        
        llm_config = settings.get_llm_config()
        api_key = llm_config.get("api_key")
        base_url = llm_config.get("base_url")
        
        if not api_key:
            logger.warning("[EmbeddingService] 未配置API Key，无法使用向量服务")
            return
            
        try:
            # 默认使用 OpenAI Embeddings
            # text-embedding-3-small 是性价比很高的选择
            self.embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                openai_api_key=api_key,
                openai_api_base=base_url
            )
            logger.info("[EmbeddingService] 向量服务初始化成功 (text-embedding-3-small)")
        except Exception as e:
            logger.error(f"[EmbeddingService] 向量服务初始化失败: {e}")

    async def embed_query(self, text: str) -> List[float]:
        """为查询生成向量"""
        if not self.embeddings:
            return []
        try:
            return await self.embeddings.aembed_query(text)
        except Exception as e:
            logger.error(f"[EmbeddingService] 向量生成失败: {e}")
            return []

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """为文档列表生成向量"""
        if not self.embeddings:
            return []
        try:
            return await self.embeddings.aembed_documents(texts)
        except Exception as e:
            logger.error(f"[EmbeddingService] 批量向量生成失败: {e}")
            return []

# 全局实例
embedding_service = EmbeddingService()
