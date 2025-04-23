import os
from typing import List

import httpx
from llama_index.vector_stores.milvus.utils import BaseSparseEmbeddingFunction
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)


class BGEM3SparseEmbeddingFunction(BaseSparseEmbeddingFunction):
    def __init__(self, timeout=60, max_retries=32):
        """
        初始化函数

        Args:
            timeout: 请求超时时间(秒)
            max_retries: 最大重试次数
        """
        self.timeout = timeout
        self.max_retries = max_retries
        super().__init__()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.RequestError,
                httpx.HTTPStatusError,
            )
        ),
        reraise=True,
    )
    def _remote_encode(self, queries: List[str]):
        """
        使用httpx连接远程的bgem3服务
        httpx请求体
        {
            "input": "Your text string goes here",
            "return_dense": "False",
            "return_sparse": "True",
            "return_colbert_vecs": "False"
        }
        httpx返回
        {
            "data": [
                {
                    "embedding": {
                        "14804": 0.185791015625,
                        "7986": 0.2783203125,
                        "79315": 0.32080078125,
                        "60899": 0.2099609375,
                        "3688": 0.29248046875
                    },
                    "index": 0,
                    "object": "sparse_embedding"
                }
            ],
            "model": "BAAI/bge-m3",
            "usage": {
                "prompt_tokens": 5,
                "total_tokens": 5
            },
            "object": "list"
        }
        """
        try:
            response = httpx.post(
                f"{os.getenv('EMBEDDING_BASE_URL')}/embeddings",
                json={
                    "input": queries,
                    "return_dense": "False",
                    "return_sparse": "True",
                    "return_colbert_vecs": "False",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()  # 检查HTTP错误
            return response.json()["data"]
        except httpx.HTTPStatusError as e:
            print(f"HTTP错误: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.TimeoutException:
            print(f"请求超时")
            raise
        except Exception as e:
            print(f"请求错误: {str(e)}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.RequestError,
                httpx.HTTPStatusError,
            )
        ),
        reraise=True,
    )
    async def _async_remote_encode(self, queries: List[str]):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{os.getenv('EMBEDDING_BASE_URL')}/embeddings",
                    json={
                        "input": queries,
                        "return_dense": "False",
                        "return_sparse": "True",
                        "return_colbert_vecs": "False",
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()  # 检查HTTP错误
                return response.json()["data"]
        except httpx.HTTPStatusError as e:
            print(f"HTTP错误: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.TimeoutException:
            print(f"请求超时")
            raise
        except Exception as e:
            print(f"请求错误: {str(e)}")
            raise

    def encode_queries(self, queries: List[str]):
        # 使用httpx连接远程的bgem3服务
        outputs = self._remote_encode(queries)
        return [self._to_standard_dict(output["embedding"]) for output in outputs]

    async def async_encode_queries(self, queries: List[str]):
        outputs = await self._async_remote_encode(queries)
        return [self._to_standard_dict(output["embedding"]) for output in outputs]

    def encode_documents(self, documents: List[str]):
        outputs = self._remote_encode(documents)
        return [self._to_standard_dict(output["embedding"]) for output in outputs]

    async def async_encode_documents(self, documents: List[str]):
        outputs = await self._async_remote_encode(documents)
        return [self._to_standard_dict(output["embedding"]) for output in outputs]

    def _to_standard_dict(self, raw_output):
        result = {}
        for k in raw_output:
            result[int(k)] = raw_output[k]
        return result
