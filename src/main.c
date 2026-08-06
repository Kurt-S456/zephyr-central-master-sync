#include <zephyr/kernel.h>

#if IS_ENABLED(CONFIG_MCO_OUTPUT_ENABLE)
#include <stm32f1xx.h>
#endif

#if IS_ENABLED(CONFIG_MCO_OUTPUT_ENABLE)
static void enable_mco_output(void)
{
	/* Enable GPIOA clock and drive PA8 as AF push-pull at high speed. */
	RCC->APB2ENR |= RCC_APB2ENR_IOPAEN;
	GPIOA->CRH &= ~(GPIO_CRH_MODE8_Msk | GPIO_CRH_CNF8_Msk);
	GPIOA->CRH |= (GPIO_CRH_MODE8_0 | GPIO_CRH_MODE8_1 | GPIO_CRH_CNF8_1);

	/* Route selected source to MCO without touching the crystal circuit. */
	RCC->CFGR &= ~RCC_CFGR_MCO;
#if IS_ENABLED(CONFIG_MCO_OUTPUT_SOURCE_HSE)
	RCC->CFGR |= RCC_CFGR_MCO_HSE;
#elif IS_ENABLED(CONFIG_MCO_OUTPUT_SOURCE_SYSCLK)
	RCC->CFGR |= RCC_CFGR_MCO_SYSCLK;
#endif
}
#endif

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
void jitter_controller_run(void);
void jitter_target_run(void);

void main(void)
{
#if IS_ENABLED(CONFIG_MCO_OUTPUT_ENABLE)
	enable_mco_output();
#endif

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
#elif IS_ENABLED(CONFIG_ROLE_JITTER_CONTROLLER)
	jitter_controller_run();
#elif IS_ENABLED(CONFIG_ROLE_JITTER_TARGET)
	jitter_target_run();
#else
#error "Select either CONFIG_ROLE_CONTROLLER or CONFIG_ROLE_TARGET"
#endif
}
