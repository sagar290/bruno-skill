package main

import (
	"net/http"
	"github.com/gin-gonic/gin"
)

// RegisterRoutes sets up the application's endpoints
func RegisterRoutes(r *gin.Engine) {
	// 1. Healthcheck endpoint
	r.GET("/api/v1/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"status": "ok"})
	})

	// 2. User resource collection endpoints
	r.GET("/api/v1/users", GetUsersHandler)
	r.POST("/api/v1/users", CreateUserHandler)

	// 3. Single User resource endpoints
	r.GET("/api/v1/users/:id", GetUserDetailHandler)
	r.PUT("/api/v1/users/:id", UpdateUserHandler)
	r.DELETE("/api/v1/users/:id", DeleteUserHandler)
}

func GetUsersHandler(c *gin.Context)     {}
func CreateUserHandler(c *gin.Context)   {}
func GetUserDetailHandler(c *gin.Context) {}
func UpdateUserHandler(c *gin.Context)   {}
func DeleteUserHandler(c *gin.Context)   {}
