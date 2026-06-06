import { reactive } from 'vue'
import { getCsrfToken } from '@utils/csrf'
import { extractApiErrorMessage } from '@utils/apiError'

// 统一的请求封装工具
const defaultHeaders = () => ({
  "Content-Type": "application/json",
  "X-CSRFToken": getCsrfToken()
});

export async function request(url, opts = {}) {
  const controller = new AbortController();
  const signal = opts.signal || controller.signal;

  try {
    const res = await fetch(url, {
      headers: { ...defaultHeaders(), ...(opts.headers || {}) },
      ...opts,
      signal
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      throw new Error(extractApiErrorMessage(data, `HTTP ${res.status}`));
    }

    return data;
  } catch (error) {
    // 如果是主动取消的请求，重新抛出
    if (error.name === 'AbortError') {
      throw error;
    }
    // 其他错误包装后抛出
    throw new Error(error.message || '网络错误');
  }
}

// 带防抖的请求
export function createDebouncedRequest(fn, delay = 400) {
  let timer = null;
  let controller = null;

  return async function(...args) {
    // 取消之前的请求
    if (controller) {
      controller.abort();
    }

    // 清除之前的定时器
    clearTimeout(timer);

    // 创建新的控制器
    controller = new AbortController();

    return new Promise((resolve, reject) => {
      timer = setTimeout(async () => {
        try {
          const result = await fn(...args, controller.signal);
          resolve(result);
        } catch (error) {
          if (error.name !== 'AbortError') {
            reject(error);
          }
        }
      }, delay);
    });
  };
}

// 倒计时Hook
export function useCountdown() {
  let timer = null;

  const countdown = reactive({
    seconds: 0,
    get counting() {
      return this.seconds > 0;
    },
    start(n = 60) {
      this.stop();
      const normalizedSeconds = Number(n);
      this.seconds = Number.isFinite(normalizedSeconds) && normalizedSeconds > 0
        ? Math.floor(normalizedSeconds)
        : 60;
      timer = setInterval(() => {
        countdown.seconds--;
        if (countdown.seconds <= 0) {
          countdown.stop();
        }
      }, 1000);
    },
    stop() {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      countdown.seconds = 0;
    },
    cleanup() {
      this.stop();
    }
  });

  // 返回清理函数，供组件卸载时调用
  return countdown;
}
