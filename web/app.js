(function () {
  'use strict';

  // =============================================
  // CONSTANTS
  // =============================================
  const CATEGORIES = [
    'numbers', 'days', 'months', 'verbs', 'nouns',
    'adjectives', 'adverbs', 'phrases', 'colors', 'greetings', 'pronouns'
  ];
  const STORAGE_KEY = 'deutsh_progress';
  const PRAISE = ['Sehr gut!', 'Richtig!', 'Perfekt!', 'Ausgezeichnet!', 'Wunderbar!', 'Toll!', 'Genau!', 'Super!'];
  const ENCOURAGE = ['Weiter so!', 'Fast!', 'Nicht aufgeben!', 'Nächstes Mal!'];

  // =============================================
  // STATE
  // =============================================
  let data = {};           // category -> array of word objects
  let progress = null;     // persisted progress
  let currentCategory = '';
  let currentDirection = 'en-de'; // or 'de-en'

  // Flashcard state
  let flashcardWords = [];
  let flashcardIndex = 0;

  // Quiz state
  let quizWords = [];
  let quizIndex = 0;
  let quizCorrect = 0;
  let quizAnswered = false;

  // Type state
  let typeWords = [];
  let typeIndex = 0;
  let typeCorrect = 0;
  let typeAnswered = false;

  // Speed state
  let speedTimer = null;
  let speedTimeLeft = 60;
  let speedScore = 0;
  let speedCorrectCount = 0;
  let speedCurrentWord = null;
  let speedRunning = false;

  // Sentences state
  let sentencesData = [];
  let sentencesFiltered = [];
  let sentencesIndex = 0;
  let sentencesCorrect = 0;
  let sentencesAnswered = false;
  let sentencesDifficulty = 'all';

  // Library state
  let libraryCategory = 'numbers';

  // =============================================
  // UTILITIES
  // =============================================
  function normalize(str) {
    return str.toLowerCase()
      .replace(/ü/g, 'u').replace(/ö/g, 'o').replace(/ä/g, 'a')
      .replace(/ß/g, 'ss').replace(/\s+/g, ' ').trim();
  }

  function shuffleArray(arr) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function getWordKey(category, word) {
    return category + ':' + word.de;
  }

  function getMastery(category, word) {
    const key = getWordKey(category, word);
    return (progress.words[key] && progress.words[key].mastery) || 0;
  }

  function updateMastery(category, word, correct) {
    const key = getWordKey(category, word);
    if (!progress.words[key]) {
      progress.words[key] = { mastery: 0, correct: 0, wrong: 0 };
    }
    const w = progress.words[key];
    if (correct) {
      w.mastery = Math.min(5, w.mastery + 1);
      w.correct++;
    } else {
      w.mastery = Math.max(0, w.mastery - 1);
      w.wrong++;
    }
    saveProgress();
  }

  function addXP(amount) {
    progress.xp += amount;
    saveProgress();
    updateDashboardStats();
  }

  function weightedSample(words, count, category) {
    const weighted = words.map(w => ({
      word: w,
      weight: 6 - getMastery(category, w)
    }));
    const result = [];
    const pool = [...weighted];
    const n = Math.min(count, pool.length);
    for (let i = 0; i < n; i++) {
      const totalWeight = pool.reduce((s, w) => s + w.weight, 0);
      let r = Math.random() * totalWeight;
      let idx = 0;
      for (let j = 0; j < pool.length; j++) {
        r -= pool[j].weight;
        if (r <= 0) { idx = j; break; }
      }
      result.push(pool[idx].word);
      pool.splice(idx, 1);
    }
    return result;
  }

  function randomPraise() {
    return PRAISE[Math.floor(Math.random() * PRAISE.length)];
  }

  function randomEncourage() {
    return ENCOURAGE[Math.floor(Math.random() * ENCOURAGE.length)];
  }

  function todayStr() {
    return new Date().toISOString().split('T')[0];
  }

  function yesterdayStr() {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    return d.toISOString().split('T')[0];
  }

  // =============================================
  // PROGRESS PERSISTENCE
  // =============================================
  function defaultProgress() {
    return { xp: 0, streak: 0, lastPlayed: '', bestSpeed: 0, words: {} };
  }

  function loadProgress() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        progress = JSON.parse(raw);
        if (!progress.words) progress.words = {};
        if (!progress.bestSpeed) progress.bestSpeed = 0;
      } else {
        progress = defaultProgress();
      }
    } catch {
      progress = defaultProgress();
    }
    // Update streak
    const today = todayStr();
    const yesterday = yesterdayStr();
    if (progress.lastPlayed === today) {
      // already played today, keep streak
    } else if (progress.lastPlayed === yesterday) {
      progress.streak++;
    } else if (progress.lastPlayed) {
      progress.streak = 1;
    } else {
      progress.streak = 1;
    }
    progress.lastPlayed = today;
    saveProgress();
  }

  function saveProgress() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
  }

  // =============================================
  // DATA LOADING
  // =============================================
  async function loadData() {
    const promises = CATEGORIES.map(async (cat) => {
      try {
        const resp = await fetch('../data/' + cat + '.json');
        data[cat] = await resp.json();
      } catch (e) {
        console.error('Failed to load ' + cat, e);
        data[cat] = [];
      }
    });
    // Also load sentences
    promises.push(
      fetch('../data/sentences.json')
        .then(r => r.json())
        .then(d => { sentencesData = d; })
        .catch(() => { sentencesData = []; })
    );
    await Promise.all(promises);
    updateDashboard();
  }

  // =============================================
  // TOAST NOTIFICATIONS
  // =============================================
  function showToast(message, type) {
    type = type || 'info';
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    const icons = { success: 'fa-check-circle', error: 'fa-times-circle', info: 'fa-info-circle' };
    toast.innerHTML = '<i class="fas ' + (icons[type] || icons.info) + '"></i> ' + message;
    container.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 3200);
  }

  // =============================================
  // SCREEN NAVIGATION
  // =============================================
  function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    const el = document.getElementById(id);
    if (el) el.classList.add('active');
    if (id === 'dashboard') updateDashboard();
  }

  // =============================================
  // DASHBOARD
  // =============================================
  function countWordsLearned() {
    let count = 0;
    for (const key in progress.words) {
      if (progress.words[key].mastery >= 3) count++;
    }
    return count;
  }

  function getCategoryMastery(cat) {
    const words = data[cat];
    if (!words || words.length === 0) return 0;
    let total = 0;
    words.forEach(w => { total += getMastery(cat, w); });
    return Math.round((total / (words.length * 5)) * 100);
  }

  function updateDashboardStats() {
    document.getElementById('stat-xp').textContent = progress.xp;
    document.getElementById('stat-streak').textContent = progress.streak;
    document.getElementById('stat-words-learned').textContent = countWordsLearned();
  }

  function updateDashboard() {
    updateDashboardStats();
    CATEGORIES.forEach(cat => {
      const card = document.querySelector('.category-card[data-category="' + cat + '"]');
      if (!card || !data[cat]) return;
      const words = data[cat];
      card.querySelector('.word-count-value').textContent = words.length + ' words';
      const pct = getCategoryMastery(cat);
      card.querySelector('.mastery-bar').style.width = pct + '%';
      card.querySelector('.mastery-percentage').textContent = pct + '% mastered';
    });
  }

  // =============================================
  // DIRECTION TOGGLE
  // =============================================
  function setupDirectionToggle(containerId, callback) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.querySelectorAll('.direction-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        container.querySelectorAll('.direction-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentDirection = btn.dataset.direction;
        if (callback) callback();
      });
    });
  }

  function getQuestion(word) {
    return currentDirection === 'en-de' ? word.en : word.de;
  }

  function getAnswer(word) {
    return currentDirection === 'en-de' ? word.de : word.en;
  }

  function getQuestionLabel() {
    return currentDirection === 'en-de' ? 'English' : 'Deutsch';
  }

  function getAnswerLabel() {
    return currentDirection === 'en-de' ? 'Deutsch' : 'English';
  }

  // =============================================
  // FLASHCARD MODE
  // =============================================
  function startFlashcards() {
    const words = data[currentCategory];
    if (!words || words.length === 0) return;
    flashcardWords = weightedSample(words, words.length, currentCategory);
    flashcardIndex = 0;
    showScreen('flashcard-mode');
    renderFlashcard();
  }

  function renderFlashcard() {
    if (flashcardIndex >= flashcardWords.length) {
      showToast('Round complete! ' + randomPraise(), 'success');
      showScreen('mode-select');
      return;
    }
    const word = flashcardWords[flashcardIndex];
    const card = document.getElementById('flashcard');
    card.classList.remove('flipped');

    document.getElementById('flashcard-front-word').textContent = getQuestion(word);
    document.getElementById('flashcard-back-word').textContent = getAnswer(word);

    const frontLabel = card.querySelector('.flashcard-front .flashcard-lang-label');
    const backLabel = card.querySelector('.flashcard-back .flashcard-lang-label');
    if (frontLabel) frontLabel.textContent = getQuestionLabel();
    if (backLabel) backLabel.textContent = getAnswerLabel();

    let hintParts = [];
    if (word.hint) hintParts.push(word.hint);
    if (word.example) hintParts.push(word.example);
    if (word.conjugation) hintParts.push(word.conjugation);
    if (word.context) hintParts.push(word.context);
    if (word.opposite) hintParts.push('Opposite: ' + word.opposite);
    const hintText = card.querySelector('.hint-text');
    if (hintText) hintText.textContent = hintParts.join(' | ') || '';
    document.getElementById('flashcard-hint').style.display = hintParts.length ? '' : 'none';

    document.getElementById('flashcard-progress').textContent =
      'Card ' + (flashcardIndex + 1) + ' of ' + flashcardWords.length;
  }

  function flipFlashcard() {
    document.getElementById('flashcard').classList.toggle('flipped');
  }

  function flashcardGotIt() {
    if (flashcardIndex >= flashcardWords.length) return;
    updateMastery(currentCategory, flashcardWords[flashcardIndex], true);
    showToast(randomPraise(), 'success');
    flashcardIndex++;
    renderFlashcard();
  }

  function flashcardStillLearning() {
    if (flashcardIndex >= flashcardWords.length) return;
    updateMastery(currentCategory, flashcardWords[flashcardIndex], false);
    showToast(randomEncourage(), 'info');
    flashcardIndex++;
    renderFlashcard();
  }

  function initFlashcards() {
    document.getElementById('flashcard').addEventListener('click', flipFlashcard);
    document.getElementById('flashcard-flip').addEventListener('click', flipFlashcard);
    document.getElementById('flashcard-got-it').addEventListener('click', flashcardGotIt);
    document.getElementById('flashcard-still-learning').addEventListener('click', flashcardStillLearning);
    document.getElementById('flashcard-back').addEventListener('click', () => showScreen('mode-select'));
    setupDirectionToggle('flashcard-direction-toggle', renderFlashcard);
  }

  // =============================================
  // QUIZ MODE
  // =============================================
  function startQuiz() {
    const words = data[currentCategory];
    if (!words || words.length === 0) return;
    quizWords = weightedSample(words, Math.min(10, words.length), currentCategory);
    quizIndex = 0;
    quizCorrect = 0;
    quizAnswered = false;
    showScreen('quiz-mode');
    updateQuizScore();
    renderQuizQuestion();
  }

  function updateQuizScore() {
    const scoreEl = document.getElementById('quiz-score');
    scoreEl.querySelector('.score-correct').textContent = quizCorrect;
    scoreEl.querySelector('.score-total').textContent = quizIndex;
  }

  function renderQuizQuestion() {
    if (quizIndex >= quizWords.length) {
      showQuizResults();
      return;
    }
    quizAnswered = false;
    const word = quizWords[quizIndex];
    const prompt = document.querySelector('.quiz-prompt');
    if (currentDirection === 'en-de') {
      prompt.textContent = 'What is the German translation of:';
    } else {
      prompt.textContent = 'What is the English translation of:';
    }
    document.getElementById('quiz-question').textContent = getQuestion(word);

    // Build options: 1 correct + 3 wrong
    const allWords = data[currentCategory];
    const wrongPool = allWords.filter(w => w.de !== word.de);
    const wrongs = shuffleArray(wrongPool).slice(0, 3);
    const options = shuffleArray([word, ...wrongs]);

    const container = document.getElementById('quiz-options');
    container.innerHTML = '';
    options.forEach((opt, i) => {
      const btn = document.createElement('button');
      btn.className = 'quiz-option-btn';
      btn.dataset.option = i;
      btn.textContent = getAnswer(opt);
      btn.dataset.de = opt.de;
      btn.addEventListener('click', () => handleQuizAnswer(btn, opt, word));
      container.appendChild(btn);
    });

    document.getElementById('quiz-feedback').style.display = 'none';
    document.getElementById('quiz-next').style.display = 'none';
  }

  function handleQuizAnswer(btn, selected, correct) {
    if (quizAnswered) return;
    quizAnswered = true;
    const isCorrect = selected.de === correct.de;
    const allBtns = document.querySelectorAll('#quiz-options .quiz-option-btn');

    allBtns.forEach(b => {
      b.classList.add('disabled');
      if (b.dataset.de === correct.de) b.classList.add('correct');
    });

    if (isCorrect) {
      btn.classList.add('correct');
      quizCorrect++;
      addXP(10);
      updateMastery(currentCategory, correct, true);
      showFeedback('quiz-feedback', true, randomPraise(), '');
    } else {
      btn.classList.add('wrong');
      updateMastery(currentCategory, correct, false);
      showFeedback('quiz-feedback', false,
        randomEncourage(),
        'Correct: ' + getAnswer(correct));
    }

    quizIndex++;
    updateQuizScore();
    document.getElementById('quiz-next').style.display = '';
  }

  function showFeedback(containerId, success, message, correction) {
    const fb = document.getElementById(containerId);
    fb.style.display = '';
    fb.className = success ? 'quiz-feedback feedback-success' : 'quiz-feedback feedback-error';
    if (containerId === 'type-feedback') {
      fb.className = success ? 'type-feedback feedback-success' : 'type-feedback feedback-error';
    }
    fb.querySelector('.feedback-icon').innerHTML = success
      ? '<i class="fas fa-check-circle"></i>'
      : '<i class="fas fa-times-circle"></i>';
    fb.querySelector('.feedback-message').textContent = message;
    const corrEl = fb.querySelector('.feedback-correct-answer') || fb.querySelector('.feedback-correction');
    if (corrEl) {
      if (correction) {
        corrEl.style.display = '';
        if (corrEl.querySelector('.correction-answer')) {
          corrEl.querySelector('.correction-answer').textContent = correction.replace('Correct: ', '');
        } else {
          corrEl.textContent = correction;
        }
      } else {
        corrEl.style.display = 'none';
      }
    }
  }

  function showQuizResults() {
    const pct = Math.round((quizCorrect / quizWords.length) * 100);
    let grade = 'Keep practicing!';
    if (pct >= 90) grade = 'Ausgezeichnet! Outstanding!';
    else if (pct >= 70) grade = 'Sehr gut! Great job!';
    else if (pct >= 50) grade = 'Gut! Keep going!';

    document.getElementById('quiz-question').textContent = grade;
    document.querySelector('.quiz-prompt').textContent =
      'Round complete! You got ' + quizCorrect + ' out of ' + quizWords.length + ' (' + pct + '%)';
    document.getElementById('quiz-options').innerHTML = '';
    document.getElementById('quiz-feedback').style.display = 'none';
    document.getElementById('quiz-next').textContent = 'Play Again';
    document.getElementById('quiz-next').style.display = '';
    document.getElementById('quiz-next').onclick = startQuiz;
  }

  function initQuiz() {
    document.getElementById('quiz-back').addEventListener('click', () => showScreen('mode-select'));
    document.getElementById('quiz-next').addEventListener('click', () => {
      renderQuizQuestion();
    });
    setupDirectionToggle('quiz-direction-toggle', null);
  }

  // =============================================
  // TYPE IT MODE
  // =============================================
  function startTypeIt() {
    const words = data[currentCategory];
    if (!words || words.length === 0) return;
    typeWords = weightedSample(words, Math.min(10, words.length), currentCategory);
    typeIndex = 0;
    typeCorrect = 0;
    typeAnswered = false;
    showScreen('type-mode');
    updateTypeScore();
    renderTypeQuestion();
  }

  function updateTypeScore() {
    const scoreEl = document.getElementById('type-score');
    scoreEl.querySelector('.score-correct').textContent = typeCorrect;
    scoreEl.querySelector('.score-total').textContent = typeIndex;
  }

  function renderTypeQuestion() {
    if (typeIndex >= typeWords.length) {
      showTypeResults();
      return;
    }
    typeAnswered = false;
    const word = typeWords[typeIndex];
    const prompt = document.querySelector('.type-prompt');
    if (currentDirection === 'en-de') {
      prompt.textContent = 'Type the German translation of:';
    } else {
      prompt.textContent = 'Type the English translation of:';
    }
    document.getElementById('type-question').textContent = getQuestion(word);
    const input = document.getElementById('type-input');
    input.value = '';
    input.disabled = false;
    input.className = 'type-input';
    input.focus();

    document.getElementById('type-feedback').style.display = 'none';
    document.getElementById('type-next').style.display = 'none';
    document.getElementById('type-submit').style.display = '';
  }

  function handleTypeSubmit() {
    if (typeAnswered) return;
    const word = typeWords[typeIndex];
    const input = document.getElementById('type-input');
    const userAnswer = input.value.trim();
    if (!userAnswer) return;

    typeAnswered = true;
    input.disabled = true;
    const correctAnswer = getAnswer(word);
    const isCorrect = normalize(userAnswer) === normalize(correctAnswer);

    if (isCorrect) {
      typeCorrect++;
      addXP(15);
      updateMastery(currentCategory, word, true);
      input.classList.add('correct');
      showTypeFeedback(true, randomPraise(), '');
    } else {
      updateMastery(currentCategory, word, false);
      input.classList.add('wrong');
      showTypeFeedback(false, randomEncourage(), correctAnswer);
    }

    typeIndex++;
    updateTypeScore();
    document.getElementById('type-next').style.display = '';
    document.getElementById('type-submit').style.display = 'none';
  }

  function showTypeFeedback(success, message, correction) {
    const fb = document.getElementById('type-feedback');
    fb.style.display = '';
    fb.className = success ? 'type-feedback feedback-success' : 'type-feedback feedback-error';
    fb.querySelector('.feedback-icon').innerHTML = success
      ? '<i class="fas fa-check-circle"></i>'
      : '<i class="fas fa-times-circle"></i>';
    fb.querySelector('.feedback-message').textContent = message;
    const correctionArea = fb.querySelector('.feedback-correction');
    if (correction) {
      correctionArea.style.display = '';
      document.getElementById('type-correct-answer').textContent = correction;
    } else {
      correctionArea.style.display = 'none';
    }
  }

  function showTypeResults() {
    const pct = Math.round((typeCorrect / typeWords.length) * 100);
    let grade = 'Keep practicing!';
    if (pct >= 90) grade = 'Ausgezeichnet! Outstanding!';
    else if (pct >= 70) grade = 'Sehr gut! Great job!';
    else if (pct >= 50) grade = 'Gut! Keep going!';

    document.getElementById('type-question').textContent = grade;
    document.querySelector('.type-prompt').textContent =
      'Round complete! You got ' + typeCorrect + ' out of ' + typeWords.length + ' (' + pct + '%)';
    document.getElementById('type-input').style.display = 'none';
    document.getElementById('type-submit').style.display = 'none';
    document.getElementById('type-feedback').style.display = 'none';
    document.getElementById('type-next').textContent = 'Play Again';
    document.getElementById('type-next').style.display = '';
    document.getElementById('type-next').onclick = () => {
      document.getElementById('type-input').style.display = '';
      startTypeIt();
    };
  }

  function initTypeIt() {
    document.getElementById('type-back').addEventListener('click', () => showScreen('mode-select'));
    document.getElementById('type-submit').addEventListener('click', handleTypeSubmit);
    document.getElementById('type-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        if (typeAnswered) {
          renderTypeQuestion();
        } else {
          handleTypeSubmit();
        }
      }
    });
    document.getElementById('type-next').addEventListener('click', () => {
      renderTypeQuestion();
    });
    setupDirectionToggle('type-direction-toggle', null);
  }

  // =============================================
  // SPEED ROUND MODE
  // =============================================
  function startSpeedRound() {
    speedScore = 0;
    speedCorrectCount = 0;
    speedTimeLeft = 60;
    speedRunning = false;

    showScreen('speed-mode');
    document.getElementById('speed-start-overlay').style.display = '';
    document.getElementById('speed-game-area').style.display = 'none';
    document.getElementById('speed-results').style.display = 'none';
    document.getElementById('speed-timer').querySelector('.timer-value').textContent = '60';
    document.getElementById('speed-score').querySelector('.speed-score-value').textContent = '0';
    document.getElementById('speed-timer').className = 'speed-timer';
  }

  function beginSpeedRound() {
    speedRunning = true;
    document.getElementById('speed-start-overlay').style.display = 'none';
    document.getElementById('speed-game-area').style.display = '';
    renderSpeedQuestion();

    speedTimer = setInterval(() => {
      speedTimeLeft -= 0.1;
      const display = Math.max(0, Math.ceil(speedTimeLeft));
      document.getElementById('speed-timer').querySelector('.timer-value').textContent = display;

      // Color changes
      const timerEl = document.getElementById('speed-timer');
      if (speedTimeLeft <= 10) timerEl.className = 'speed-timer danger';
      else if (speedTimeLeft <= 25) timerEl.className = 'speed-timer warning';
      else timerEl.className = 'speed-timer';

      if (speedTimeLeft <= 0) {
        clearInterval(speedTimer);
        speedRunning = false;
        endSpeedRound();
      }
    }, 100);
  }

  function renderSpeedQuestion() {
    if (!speedRunning) return;
    const words = data[currentCategory];
    if (!words || words.length < 4) return;

    // Pick a random word
    speedCurrentWord = words[Math.floor(Math.random() * words.length)];
    document.getElementById('speed-question').textContent = speedCurrentWord.en;

    // Build options
    const wrongPool = words.filter(w => w.de !== speedCurrentWord.de);
    const wrongs = shuffleArray(wrongPool).slice(0, 3);
    const options = shuffleArray([speedCurrentWord, ...wrongs]);

    const container = document.getElementById('speed-options');
    container.innerHTML = '';
    options.forEach((opt, i) => {
      const btn = document.createElement('button');
      btn.className = 'speed-option-btn';
      btn.textContent = opt.de;
      btn.addEventListener('click', () => handleSpeedAnswer(btn, opt));
      container.appendChild(btn);
    });
  }

  function handleSpeedAnswer(btn, selected) {
    if (!speedRunning) return;
    const isCorrect = selected.de === speedCurrentWord.de;
    if (isCorrect) {
      speedScore += 5;
      speedCorrectCount++;
      addXP(5);
      updateMastery(currentCategory, speedCurrentWord, true);
      btn.classList.add('correct');
    } else {
      btn.classList.add('wrong');
      updateMastery(currentCategory, speedCurrentWord, false);
    }
    document.getElementById('speed-score').querySelector('.speed-score-value').textContent = speedScore;

    setTimeout(() => {
      if (speedRunning) renderSpeedQuestion();
    }, isCorrect ? 200 : 400);
  }

  function endSpeedRound() {
    document.getElementById('speed-game-area').style.display = 'none';
    document.getElementById('speed-results').style.display = '';
    document.getElementById('speed-final-score').textContent = speedScore;
    document.getElementById('speed-correct-count').textContent = speedCorrectCount;

    if (speedScore > progress.bestSpeed) {
      progress.bestSpeed = speedScore;
      saveProgress();
      showToast('New personal best: ' + speedScore + '!', 'success');
    }
    document.getElementById('speed-personal-best').textContent = progress.bestSpeed;
  }

  function initSpeedRound() {
    document.getElementById('speed-back').addEventListener('click', () => {
      if (speedTimer) clearInterval(speedTimer);
      speedRunning = false;
      showScreen('mode-select');
    });
    document.getElementById('speed-start-btn').addEventListener('click', beginSpeedRound);
    document.getElementById('speed-play-again').addEventListener('click', () => {
      startSpeedRound();
      // small delay then start
      setTimeout(() => beginSpeedRound(), 100);
    });
    document.getElementById('speed-results-back').addEventListener('click', () => showScreen('mode-select'));
  }

  // =============================================
  // EVENT HANDLERS & INIT
  // =============================================
  function initCategoryCards() {
    document.querySelectorAll('.category-card').forEach(card => {
      card.addEventListener('click', () => {
        currentCategory = card.dataset.category;
        document.getElementById('mode-category-name').textContent =
          currentCategory.charAt(0).toUpperCase() + currentCategory.slice(1);
        showScreen('mode-select');
      });
    });
  }

  function initModeCards() {
    document.querySelectorAll('.mode-card').forEach(card => {
      card.addEventListener('click', () => {
        const mode = card.dataset.mode;
        if (mode === 'flashcards') startFlashcards();
        else if (mode === 'quiz') startQuiz();
        else if (mode === 'type-it') startTypeIt();
        else if (mode === 'speed-round') startSpeedRound();
      });
    });
    document.getElementById('mode-select-back').addEventListener('click', () => showScreen('dashboard'));
  }

  function initKeyboard() {
    document.addEventListener('keydown', (e) => {
      const activeScreen = document.querySelector('.screen.active');
      if (!activeScreen) return;
      const id = activeScreen.id;

      if (id === 'flashcard-mode') {
        if (e.code === 'Space') { e.preventDefault(); flipFlashcard(); }
        else if (e.key === 'ArrowRight') { e.preventDefault(); flashcardGotIt(); }
        else if (e.key === 'ArrowLeft') { e.preventDefault(); flashcardStillLearning(); }
      } else if (id === 'quiz-mode') {
        if (e.key >= '1' && e.key <= '4') {
          const btns = document.querySelectorAll('#quiz-options .quiz-option-btn');
          const idx = parseInt(e.key) - 1;
          if (btns[idx]) btns[idx].click();
        }
      }
    });
  }

  // =============================================
  // LIBRARY MODE
  // =============================================
  function showLibrary(cat) {
    libraryCategory = cat || CATEGORIES[0];
    showScreen('library-mode');
    renderLibraryTabs();
    renderLibraryTable();
  }

  function renderLibraryTabs() {
    const container = document.getElementById('library-tabs');
    container.innerHTML = '';
    CATEGORIES.forEach(cat => {
      const btn = document.createElement('button');
      btn.className = 'library-tab' + (cat === libraryCategory ? ' active' : '');
      btn.textContent = cat.charAt(0).toUpperCase() + cat.slice(1);
      btn.addEventListener('click', () => {
        libraryCategory = cat;
        container.querySelectorAll('.library-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderLibraryTable();
      });
      container.appendChild(btn);
    });
  }

  function renderLibraryTable(filter) {
    const tbody = document.getElementById('library-table-body');
    tbody.innerHTML = '';
    const words = data[libraryCategory] || [];
    const search = (filter || '').toLowerCase();

    words.forEach(w => {
      if (search && !w.de.toLowerCase().includes(search) && !w.en.toLowerCase().includes(search)) return;
      const mastery = getMastery(libraryCategory, w);
      const stars = Array.from({length: 5}, (_, i) => i < mastery ? '\u2605' : '\u2606').join('');
      const tr = document.createElement('tr');
      tr.innerHTML =
        '<td class="lib-de">' + escapeHtml(w.de) + '</td>' +
        '<td class="lib-en">' + escapeHtml(w.en) + '</td>' +
        '<td class="lib-hint">' + escapeHtml(w.hint || '') + '</td>' +
        '<td class="lib-mastery"><span class="mastery-stars">' + stars + '</span></td>';
      tbody.appendChild(tr);
    });
  }

  function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function initLibrary() {
    document.getElementById('open-library').addEventListener('click', () => showLibrary());
    document.getElementById('library-back').addEventListener('click', () => showScreen('dashboard'));
    document.getElementById('library-search').addEventListener('input', (e) => {
      renderLibraryTable(e.target.value);
    });
  }

  // =============================================
  // SENTENCES / READING COMPREHENSION
  // =============================================
  function startSentences() {
    sentencesIndex = 0;
    sentencesCorrect = 0;
    sentencesAnswered = false;

    // Filter by difficulty
    if (sentencesDifficulty === 'all') {
      sentencesFiltered = shuffleArray([...sentencesData]);
    } else {
      const diff = parseInt(sentencesDifficulty);
      sentencesFiltered = shuffleArray(sentencesData.filter(s => s.difficulty === diff));
    }
    sentencesFiltered = sentencesFiltered.slice(0, 10);

    showScreen('sentences-mode');
    document.getElementById('sentences-start').style.display = 'none';
    document.getElementById('sentences-game').style.display = '';
    document.getElementById('sentences-results').style.display = 'none';
    updateSentencesScore();
    renderSentence();
  }

  function updateSentencesScore() {
    const scoreEl = document.getElementById('sentences-score');
    scoreEl.querySelector('.score-correct').textContent = sentencesCorrect;
    scoreEl.querySelector('.score-total').textContent = sentencesIndex;
  }

  function renderSentence() {
    if (sentencesIndex >= sentencesFiltered.length) {
      showSentencesResults();
      return;
    }
    sentencesAnswered = false;
    const s = sentencesFiltered[sentencesIndex];
    document.getElementById('sentence-de').textContent = s.de;

    const hintEl = document.getElementById('sentence-hint');
    if (s.hint) {
      hintEl.style.display = '';
      hintEl.querySelector('.hint-text').textContent = s.hint;
    } else {
      hintEl.style.display = 'none';
    }

    // Build options: 1 correct + 3 wrong
    const wrongPool = sentencesData.filter(x => x.en !== s.en);
    const wrongs = shuffleArray(wrongPool).slice(0, 3);
    const options = shuffleArray([s, ...wrongs]);

    const container = document.getElementById('sentence-options');
    container.innerHTML = '';
    options.forEach(opt => {
      const btn = document.createElement('button');
      btn.className = 'quiz-option-btn';
      btn.textContent = opt.en;
      btn.addEventListener('click', () => handleSentenceAnswer(btn, opt, s));
      container.appendChild(btn);
    });

    document.getElementById('sentence-feedback').style.display = 'none';
    document.getElementById('sentence-next').style.display = 'none';
  }

  function handleSentenceAnswer(btn, selected, correct) {
    if (sentencesAnswered) return;
    sentencesAnswered = true;
    const isCorrect = selected.en === correct.en;
    const allBtns = document.querySelectorAll('#sentence-options .quiz-option-btn');

    allBtns.forEach(b => {
      b.classList.add('disabled');
      if (b.textContent === correct.en) b.classList.add('correct');
    });

    const fb = document.getElementById('sentence-feedback');
    fb.style.display = '';
    if (isCorrect) {
      btn.classList.add('correct');
      sentencesCorrect++;
      addXP(10);
      fb.className = 'sentence-feedback feedback-success';
      fb.querySelector('.feedback-icon').innerHTML = '<i class="fas fa-check-circle"></i>';
      fb.querySelector('.feedback-message').textContent = randomPraise();
      fb.querySelector('.feedback-correct-answer').textContent = '';
    } else {
      btn.classList.add('wrong');
      fb.className = 'sentence-feedback feedback-error';
      fb.querySelector('.feedback-icon').innerHTML = '<i class="fas fa-times-circle"></i>';
      fb.querySelector('.feedback-message').textContent = randomEncourage();
      fb.querySelector('.feedback-correct-answer').textContent = 'Correct: ' + correct.en;
    }

    sentencesIndex++;
    updateSentencesScore();
    document.getElementById('sentence-next').style.display = '';
  }

  function showSentencesResults() {
    document.getElementById('sentences-game').style.display = 'none';
    document.getElementById('sentences-results').style.display = '';
    document.getElementById('sentences-final-score').textContent = sentencesCorrect;
    document.getElementById('sentences-total-count').textContent = sentencesFiltered.length;
  }

  function initSentences() {
    document.getElementById('open-sentences').addEventListener('click', () => {
      showScreen('sentences-mode');
      document.getElementById('sentences-start').style.display = '';
      document.getElementById('sentences-game').style.display = 'none';
      document.getElementById('sentences-results').style.display = 'none';
    });
    document.getElementById('sentences-back').addEventListener('click', () => showScreen('dashboard'));
    document.getElementById('sentences-start-btn').addEventListener('click', startSentences);
    document.getElementById('sentence-next').addEventListener('click', renderSentence);
    document.getElementById('sentences-play-again').addEventListener('click', startSentences);
    document.getElementById('sentences-done').addEventListener('click', () => showScreen('dashboard'));

    // Difficulty toggle
    document.querySelectorAll('#sentences-difficulty .direction-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#sentences-difficulty .direction-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        sentencesDifficulty = btn.dataset.diff;
      });
    });
  }

  // =============================================
  // BOOTSTRAP
  // =============================================
  document.addEventListener('DOMContentLoaded', async () => {
    loadProgress();
    await loadData();
    initCategoryCards();
    initModeCards();
    initFlashcards();
    initQuiz();
    initTypeIt();
    initSpeedRound();
    initLibrary();
    initSentences();
    initKeyboard();
    showToast('Willkommen! Ready to learn German?', 'info');
  });

})();
