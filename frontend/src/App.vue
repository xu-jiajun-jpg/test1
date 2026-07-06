<template>
  <router-view />
</template>

<script>
export default { name: 'App' }
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #app { height: 100%; font-family: 'Microsoft YaHei', -apple-system, system-ui, sans-serif; background: #f0f2f5; }

/* 全局滚动条 */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #f0f0f0; border-radius: 3px; }
::-webkit-scrollbar-thumb { background: #c0c4cc; border-radius: 3px; }

/* 全局卡片样式 */
.el-card { border-radius: 12px !important; border: none !important; }
.el-card__header { border-bottom: 1px solid #f0f0f0 !important; padding: 14px 20px !important; font-weight: 600 !important; }

/* 全局表格 */
.el-table th { background: #fafafa !important; font-weight: 600 !important; color: #303133 !important; }
.el-table--striped .el-table__body tr.el-table__row--striped td { background: #fafbfc !important; }

/* 全局标签 */
.el-tag { border-radius: 6px !important; font-weight: 500 !important; }

/* 全局按钮 */
.el-button { border-radius: 8px !important; font-weight: 500 !important; }
</style>
