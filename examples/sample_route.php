<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\HealthController;
use App\Http\Controllers\UserController;

// 1. Healthcheck endpoint
Route::get('/api/v1/health', [HealthController::class, 'index']);

// 2. User resource endpoints
Route::get('/api/v1/users', [UserController::class, 'index']);
Route::post('/api/v1/users', [UserController::class, 'store']);
Route::get('/api/v1/users/{id}', [UserController::class, 'show']);
Route::put('/api/v1/users/{id}', [UserController::class, 'update']);
Route::delete('/api/v1/users/{id}', [UserController::class, 'destroy']);