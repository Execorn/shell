#pragma once

#include <qassert.h>
#include <qtypes.h>

#include <algorithm>
#include <functional>
#include <span>
#include <vector>

namespace caelestia::util {

template <typename T>
class RingBuffer {
public:
    explicit RingBuffer(qsizetype capacity = 0)
        : m_data(static_cast<size_t>(std::max(capacity, static_cast<qsizetype>(0)))) {}

    [[nodiscard]] qsizetype capacity() const {
        return std::ssize(m_data);
    }

    [[nodiscard]] qsizetype count() const {
        return m_count;
    }

    void push(const T& value) {
        const auto cap = capacity();
        if (cap == 0) {
            return;
        }

        *(m_data.begin() + m_head) = value;
        m_head = (m_head + 1) % cap;
        m_count = std::min(m_count + 1, cap);
    }

    template <typename U, typename Convert = std::identity>
    void push(std::span<const U> values, Convert convert = {}) {
        const auto cap = capacity();
        if (cap == 0) {
            return;
        }

        if (std::ssize(values) > cap) {
            values = values.last(static_cast<size_t>(cap));
        }

        const qsizetype n = std::ssize(values);
        const auto firstRun = std::min(n, cap - m_head);
        std::transform(values.begin(), values.begin() + firstRun, m_data.begin() + m_head, convert);
        std::transform(values.begin() + firstRun, values.end(), m_data.begin(), convert);

        m_head = (m_head + n) % cap;
        m_count = std::min(m_count + n, cap);
    }

    template <typename U, typename Convert = std::identity>
    void copyLatest(std::span<U> out, Convert convert = {}) const {
        const auto n = std::min<qsizetype>(std::ssize(out), m_count);
        if (n == 0) {
            return;
        }

        const auto cap = capacity();
        const auto start = (m_head - n + cap) % cap;
        const auto firstRun = std::min(n, cap - start);
        std::transform(m_data.begin() + start, m_data.begin() + start + firstRun, out.begin(), convert);
        std::transform(m_data.begin(), m_data.begin() + (n - firstRun), out.begin() + firstRun, convert);
    }

    void pushTo(RingBuffer& other) const {
        if (m_count == 0) {
            return;
        }

        const std::span<const T> data(m_data);
        const auto cap = capacity();
        const auto start = (m_head - m_count + cap) % cap;
        const auto firstRun = std::min(m_count, cap - start);
        other.push(data.subspan(static_cast<size_t>(start), static_cast<size_t>(firstRun)));
        other.push(data.first(static_cast<size_t>(m_count - firstRun)));
    }

    [[nodiscard]] const T& at(qsizetype index) const {
        Q_ASSERT(index >= 0 && index < m_count);
        const auto cap = capacity();
        return *(m_data.begin() + (m_head - m_count + index + cap) % cap);
    }

    void clear() {
        m_head = 0;
        m_count = 0;
    }

private:
    std::vector<T> m_data;
    qsizetype m_head = 0;
    qsizetype m_count = 0;
};

} // namespace caelestia::util
