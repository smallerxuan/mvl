/*
 * mvl_version.h —— MVL 库版本号（语义化版本）
 *
 * 发布新版本时修改本文件，并与 CHANGELOG.md 保持一致。
 * 编译期：用 MVL_VERSION_MAJOR/MINOR/PATCH 或 MVL_VERSION_NUMBER 做条件判断；
 * 运行期：直接打印 MVL_VERSION_STRING（如启动日志上报固件所用库版本）。
 */
#ifndef _MVL_VERSION_H_
#define _MVL_VERSION_H_

#define MVL_VERSION_MAJOR   0
#define MVL_VERSION_MINOR   1
#define MVL_VERSION_PATCH   0

/* 字符串化辅助宏（两层展开才能展开数值宏） */
#define MVL_STR_(x)         #x
#define MVL_STR(x)          MVL_STR_(x)

/* "0.1.0" 形式，可直接打印 */
#define MVL_VERSION_STRING  MVL_STR(MVL_VERSION_MAJOR) "." \
                            MVL_STR(MVL_VERSION_MINOR) "." \
                            MVL_STR(MVL_VERSION_PATCH)

/* 0x000100 形式的单一数值，便于编译期比较（如 #if MVL_VERSION_NUMBER >= 0x000200） */
#define MVL_VERSION_NUMBER  ((MVL_VERSION_MAJOR << 16) | \
                             (MVL_VERSION_MINOR << 8)  | \
                             (MVL_VERSION_PATCH))

#endif /* _MVL_VERSION_H_ */
