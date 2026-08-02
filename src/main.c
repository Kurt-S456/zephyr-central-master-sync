#include <zephyr/kernel.h>

#if IS_ENABLED(CONFIG_SYNTHETIC_LOAD_TEST)
K_THREAD_STACK_DEFINE(load_thread_stack, CONFIG_SYNTHETIC_LOAD_STACKSIZE);
static struct k_thread load_thread_data;

static void dummy_load_thread(void *arg1, void *arg2, void *arg3)
{
	ARG_UNUSED(arg1);
	ARG_UNUSED(arg2);
	ARG_UNUSED(arg3);

	while (1) {
		volatile uint32_t count = 0U;

		for (int i = 0; i < CONFIG_SYNTHETIC_LOAD_LOOP_ITERS; i++) {
			count++;
		}

		if (CONFIG_SYNTHETIC_LOAD_BUSY_WAIT_US > 0) {
			k_busy_wait(CONFIG_SYNTHETIC_LOAD_BUSY_WAIT_US);
		}
	}
}
#endif

void controller_run(void);
void target_run(void);

void main(void)
{
#if IS_ENABLED(CONFIG_SYNTHETIC_LOAD_TEST)
	k_thread_create(&load_thread_data,
				load_thread_stack,
				K_THREAD_STACK_SIZEOF(load_thread_stack),
				dummy_load_thread,
				NULL,
				NULL,
				NULL,
				CONFIG_SYNTHETIC_LOAD_PRIORITY,
				0,
				K_NO_WAIT);
	k_thread_name_set(&load_thread_data, "dummy_load");
#endif

#if IS_ENABLED(CONFIG_ROLE_CONTROLLER)
	controller_run();
#elif IS_ENABLED(CONFIG_ROLE_TARGET)
	target_run();
#else
#error "Select either CONFIG_ROLE_CONTROLLER or CONFIG_ROLE_TARGET"
#endif
}
