"""启动后端（不带热重载）"""
import uvicorn
import sys
sys.dont_write_bytecode = True

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8003,
        reload=False,
        log_level="info",
    )
