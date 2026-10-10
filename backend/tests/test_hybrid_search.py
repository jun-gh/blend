import math
import unittest

from app.services.hybrid_search import _cosine_similarity, _rrf_merge


class TestHybridSearch(unittest.TestCase):
    def test_cosine_similarity_identical(self):
        vec = [1.0, 0.0, 0.0]
        self.assertAlmostEqual(_cosine_similarity(vec, vec), 1.0)

    def test_cosine_similarity_orthogonal(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        self.assertAlmostEqual(_cosine_similarity(a, b), 0.0)

    def test_cosine_similarity_empty(self):
        self.assertAlmostEqual(_cosine_similarity([], []), 0.0)

    def test_rrf_merge_combines_results(self):
        dense = [
            {"chunk_id": 1, "document_id": 1, "document_title": "Doc A", "content": "alpha", "score": 0.9},
            {"chunk_id": 2, "document_id": 1, "document_title": "Doc A", "content": "beta", "score": 0.7},
        ]
        sparse = [
            {"chunk_id": 2, "document_id": 1, "document_title": "Doc A", "content": "beta", "score": 5.0},
            {"chunk_id": 3, "document_id": 2, "document_title": "Doc B", "content": "gamma", "score": 3.0},
        ]
        results = _rrf_merge(dense, sparse, dense_weight=0.6, sparse_weight=0.4, top_k=3)
        chunk_ids = [r.chunk_id for r in results]
        self.assertIn(2, chunk_ids)
        self.assertLessEqual(len(results), 3)


if __name__ == "__main__":
    unittest.main()
