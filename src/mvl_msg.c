#include "mvl/mvl_msg.h"
#include "mvl/mvl_port.h"

typedef struct {
    mvl_action_t action;
    void *ctx;
} mvl_msg_t;

static void *s_msg_queue = NULL;

void mvl_msg_init(void)
{
    s_msg_queue = mvl_port_queue_create(MVL_MSG_QUEUE_DEPTH, sizeof(mvl_msg_t));
    mvl_port_assert(s_msg_queue != NULL);
}

void mvl_msg_post(mvl_action_t action, void *ctx)
{
    mvl_port_assert(action != NULL);

    mvl_msg_t msg = {
        .action = action,
        .ctx = ctx
    };

    /* 队列满时永久阻塞直到投递成功（关键事件不丢） */
    mvl_port_queue_send(s_msg_queue, &msg, MVL_PORT_WAIT_FOREVER);
}

bool mvl_msg_try_post(mvl_action_t action, void *ctx)
{
    mvl_port_assert(action != NULL);

    mvl_msg_t msg = { .action = action, .ctx = ctx };

    return mvl_port_queue_send(s_msg_queue, &msg, 0) == MVL_PORT_OK;
}

void mvl_msg_post_isr(mvl_action_t action, void *ctx)
{
    mvl_port_assert(action != NULL);

    mvl_msg_t msg = {
        .action = action,
        .ctx = ctx
    };

    mvl_port_queue_send_isr(s_msg_queue, &msg);
}

void mvl_msg_process(void)
{
    if (s_msg_queue == NULL) return;

    mvl_msg_t msg;

    /* 非阻塞（0 超时），一次性处理完所有待处理消息 */
    while (mvl_port_queue_receive(s_msg_queue, &msg, 0) == MVL_PORT_OK) {
        if (msg.action != NULL) {
            msg.action(msg.ctx);
        }
    }
}
