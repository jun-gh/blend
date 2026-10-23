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
            {
                "chunk_id": 1,
                "document_id": 1,
                "document_title": "Doc A",
                "content": "alpha",
                "score": 0.9,
            },
            {
                "chunk_id": 2,
                "document_id": 1,
                "document_title": "Doc A",
                "content": "beta",
                "score": 0.7,
            },
        ]
        sparse = [
            {
                "chunk_id": 2,
                "document_id": 1,
                "document_title": "Doc A",
                "content": "beta",
                "score": 5.0,
            },
            {
                "chunk_id": 3,
                "document_id": 2,
                "document_title": "Doc B",
                "content": "gamma",
                "score": 3.0,
            },
        ]
        results = _rrf_merge(dense, sparse, dense_weight=0.6, sparse_weight=0.4, top_k=3)
        chunk_ids = [r.chunk_id for r in results]
        self.assertIn(2, chunk_ids)
        self.assertLessEqual(len(results), 3)

    def test_rrf_merge_prunes_unrelated_chunks_single_match(self):
        """When only 1 chunk is relevant, non-related chunks are pruned instead of filling 5."""
        dense = [
            {
                "chunk_id": 1, "document_id": 1, "document_title": "CV",
                "score": 0.86, "content": "1",
            },
            {
                "chunk_id": 2, "document_id": 1, "document_title": "CV",
                "score": 0.52, "content": "2",
            },
            {
                "chunk_id": 3, "document_id": 1, "document_title": "CV",
                "score": 0.48, "content": "3",
            },
            {
                "chunk_id": 4, "document_id": 1, "document_title": "CV",
                "score": 0.46, "content": "4",
            },
            {
                "chunk_id": 5, "document_id": 1, "document_title": "CV",
                "score": 0.45, "content": "5",
            },
        ]
        # Only chunk 1 matched keyword 2016 in sparse search
        sparse = [
            {
                "chunk_id": 1, "document_id": 1, "document_title": "CV",
                "score": 10.0, "content": "1",
            }
        ]

        results = _rrf_merge(
            dense,
            sparse,
            dense_weight=0.6,
            sparse_weight=0.4,
            top_k=5,
            min_similarity=0.50,
            relative_threshold=0.80,
        )

        # Only chunk 1 is within 0.80 of top similarity (0.86 * 0.80 = 0.688)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk_id, 1)

    def test_rrf_merge_retains_two_related_chunks_when_both_relevant(self):
        """When 2 chunks are related, both are retained up to maximum 5."""
        dense = [
            {
                "chunk_id": 1, "document_id": 1, "document_title": "CV",
                "score": 0.84, "content": "1",
            },
            {
                "chunk_id": 2, "document_id": 1, "document_title": "CV",
                "score": 0.78, "content": "2",
            },
            {
                "chunk_id": 3, "document_id": 1, "document_title": "CV",
                "score": 0.51, "content": "3",
            },
            {
                "chunk_id": 4, "document_id": 1, "document_title": "CV",
                "score": 0.45, "content": "4",
            },
        ]
        sparse = []

        results = _rrf_merge(
            dense,
            sparse,
            dense_weight=0.6,
            sparse_weight=0.4,
            top_k=5,
            min_similarity=0.50,
            relative_threshold=0.80,
        )

        chunk_ids = [r.chunk_id for r in results]
        self.assertEqual(len(results), 2)
        self.assertEqual(chunk_ids, [1, 2])

    def test_is_header_or_contact_query_classification(self):
        from app.services.hybrid_search import is_header_or_contact_query

        self.assertTrue(is_header_or_contact_query("What is my email address?"))
        self.assertTrue(is_header_or_contact_query("What is the email address on my CV?"))
        self.assertTrue(is_header_or_contact_query("Where do I live?"))
        self.assertTrue(is_header_or_contact_query("What is my phone number?"))
        self.assertTrue(is_header_or_contact_query("Who is the author of this document?"))
        self.assertTrue(is_header_or_contact_query("Who am I?"))
        self.assertTrue(is_header_or_contact_query("Give me a summary overview"))

        self.assertFalse(is_header_or_contact_query("What is my job last 2016?"))
        self.assertFalse(is_header_or_contact_query("How is the weather today?"))
        self.assertFalse(is_header_or_contact_query("Explain how Kubernetes ingress works"))

    def test_build_fts_query_expansion(self):
        from app.services.hybrid_search import build_fts_query

        fts_email = build_fts_query("What is my email address?")
        self.assertIn("email", fts_email)
        self.assertIn("gmail*", fts_email)
        self.assertIn("OR", fts_email)

        fts_job = build_fts_query("What is my job last 2016?")
        self.assertIn("2016", fts_job)
        self.assertIn("job", fts_job)


if __name__ == "__main__":
    unittest.main()

