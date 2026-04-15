<script setup>
const props = defineProps({
  text: String,
})
</script>

<template>
  <div class="one-liner">
    <p class="liner-text">"{{ text }}"</p>
  </div>
</template>

<style scoped>
.one-liner {
  text-align: center;
  padding: 32px 16px;
  margin-bottom: 24px;
}

.liner-text {
  font-size: 20px;
  font-weight: 600;
  color: #d4a574;
  line-height: 1.6;
  font-style: italic;
}
</style>
