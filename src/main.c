#include <zephyr/kernel.h>

void controller_run(void);
void target_run(void);

void main(void)
{
#if IS_ENABLED(CONFIG_ROLE_CONTROLLER)
	controller_run();
#elif IS_ENABLED(CONFIG_ROLE_TARGET)
	target_run();
#else
#error "Select either CONFIG_ROLE_CONTROLLER or CONFIG_ROLE_TARGET"
#endif
}
