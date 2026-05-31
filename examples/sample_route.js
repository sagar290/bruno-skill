const express = require('express');
const router = express.Router();

// 1. Post management endpoints (Express style)
router.get('/api/v2/posts', (req, res) => {
    res.json({ posts: [] });
});

router.post('/api/v2/posts', (req, res) => {
    res.status(201).json({ success: true });
});

// 2. Single Post actions (with route parameters)
router.get('/api/v2/posts/:id', (req, res) => {
    res.json({ id: req.params.id });
});

router.put('/api/v2/posts/:id', (req, res) => {
    res.json({ updated: true });
});

router.delete('/api/v2/posts/:id', (req, res) => {
    res.status(204).send();
});

module.exports = router;
