# Introduction to RAG (Retrieval-Augmented Generation)

## What you will learn

Welcome! In this lesson, you will learn about RAG. RAG is one of the most used ideas in AI today.

By the end of this lesson, you will know three things:

- what RAG is,
- why people use it,
- how it works, step by step.

You do not need coding or maths. Just read slowly, one section at a time.

## Why does this matter?

You have probably used ChatGPT. ChatGPT is an LLM. LLM stands for "large language model". It is a computer program that learned from a huge amount of text. Because of this, it can answer questions and write like a person.

But an LLM has three big problems.

First, it learned from text only up to a certain date. So it does not know about things that happened after that date. Even if you ask clearly, it cannot tell you about them.

Second, it never saw your private documents. It has not read your college notices or your company's rules.

Third, sometimes it does not know the answer, but it still gives one. The answer sounds sure, but it is wrong. This is called hallucination. Hallucination means the AI makes up an answer that is not true.

Think about a closed-book exam. A student who did not study may still write something. It may sound good, but it may be wrong. An LLM can do the same thing.

So we need a way to give the LLM the right information at the right time. That way is RAG.

## What is RAG?

Think about an open-book exam. In an open-book exam, you may keep your textbook with you. You do not need to remember everything. First, you find the right page. Then you keep that page next to the question. Then you write your answer from that page.

RAG works like an open-book exam for an LLM.

RAG stands for Retrieval-Augmented Generation. Let us understand each word.

- **Retrieval** means finding. The system finds useful information from a collection of documents. This collection is called the knowledge source. It can be PDFs, web pages, notes or help pages.
- **Augmented** means "added to". The system adds the found information to your question. The question and the found information together are called the prompt. A prompt is the text we send to the LLM.
- **Generation** means writing. The LLM writes the answer using that information.

In simple words, RAG means: first find the right information, then add it to the question, then let the LLM write the answer.

The finding step is done by a separate search part of the system. The LLM does not do the search by itself.

## How does it work?

RAG works in two stages. The first stage is preparation. It happens once, before anyone asks a question. The second stage happens every time someone asks a question.

**Stage 1: Preparation**

1. **Cut the documents into pieces.** Long documents are cut into small pieces. Each piece is called a chunk. A chunk is often one short paragraph.
2. **Turn each chunk into numbers.** A computer program changes each chunk into an embedding. An embedding is a list of numbers that shows the meaning of the text. Texts with similar meaning get similar numbers, even if they use different words. A list of numbers like this is also called a vector.
3. **Save the numbers.** All the embeddings are saved in a vector database. A vector database is a store that can quickly find embeddings that are close to each other.

**Stage 2: Answering a question**

1. **Turn the question into numbers.** Your question also becomes an embedding.
2. **Find the closest chunks.** The system compares the question's embedding with the saved embeddings. It picks the few chunks whose meaning is closest. This is called similarity search. Similarity search means finding the texts whose meaning is most like your question.
3. **Add the chunks to the prompt.** The system puts the best chunks and your question together in one prompt.
4. **Write the answer.** The LLM reads the prompt and writes the answer from the chunks.

Remember the open-book exam. Stage 1 is like making an index for your textbook, so you can find pages fast. Stage 2 is like finding the right page and writing your answer from it.

## A full example, step by step

Meena is a first-year student at a college in Hyderabad. Her college has a help chatbot. The chatbot uses RAG to answer from the college notices.

**Step 1: The documents.** During preparation, the notices were cut into chunks. Here are three of them:

> Chunk A: "Applications for the merit scholarship close on 31 August."
>
> Chunk B: "To apply for the merit scholarship, you need at least 75% marks in Class 12."
>
> Chunk C: "The hostel fee must be paid by 15 July."

**Step 2: The question.** Meena types:

> "What marks do I need for the merit scholarship, and what is the last date to apply?"

**Step 3: Retrieval.** The system turns her question into an embedding. Chunk B is closest in meaning, because it talks about marks for the scholarship. Chunk A comes next, because it gives the last date. Chunk C is about the hostel fee, so it is not picked.

**Step 4: The prompt.** The system sends this text to the LLM:

> "Answer the question using only the information below.
> Information: To apply for the merit scholarship, you need at least 75% marks in Class 12. Applications for the merit scholarship close on 31 August.
> Question: What marks do I need for the merit scholarship, and what is the last date to apply?"

**Step 5: The answer.** The LLM replies:

> "You need at least 75% marks in Class 12. The last date to apply is 31 August."

The LLM never saw these college notices during its training. It could answer correctly only because RAG found the right chunks and gave them to it.

## Where can it go wrong?

RAG is very useful, but it is not perfect.

- **Wrong chunks.** If the search picks the wrong chunks, the answer can be wrong.
- **Missing information.** If the answer is not in the documents, RAG cannot find it. The LLM may still guess.
- **Bad chunk size.** An LLM can read only a limited amount of text at one time. If chunks are too big, they waste this space. If chunks are too small, they lose their meaning.

So RAG reduces hallucination, but it does not remove it completely. A good RAG system shows which chunks it used. Then a person can check the answer.

Also remember: RAG does not change the LLM itself. The LLM is not trained again. It does not keep the information after it answers. For the next question, the system searches again.

## Key takeaways

- An LLM does not know new or private information, and it can make up answers.
- RAG means Retrieval-Augmented Generation: find information, add it to the question, then write the answer.
- In preparation, documents are cut into chunks, turned into embeddings, and saved in a vector database.
- For each question, the system finds the closest chunks and adds them to the prompt.
- To change what the system knows, you only change the documents. You do not need to train the LLM again.
- RAG is used in company help chatbots, in tools that answer questions from office or college documents, and in study helpers that answer from your own notes.
- RAG reduces mistakes, but the answer is only as good as the chunks it finds.

## Glossary

- **LLM (large language model)**: a computer program that learned from a lot of text and can write answers.
- **Hallucination**: when an AI gives an answer that sounds sure but is not true.
- **RAG**: Retrieval-Augmented Generation; a way to give an LLM the right information before it answers.
- **Retrieval**: finding useful information.
- **Augmented**: added to.
- **Generation**: writing the answer.
- **Knowledge source**: the collection of documents the system searches.
- **Prompt**: the text we send to the LLM.
- **Chunk**: a small piece of a document.
- **Embedding**: a list of numbers that shows the meaning of a text.
- **Vector**: a list of numbers.
- **Vector database**: a store that saves embeddings and finds similar ones quickly.
- **Similarity search**: finding texts whose meaning is closest to the question.
- **Index**: a list that helps you find things quickly, like the index at the back of a book.

## Check your understanding

**Q1.** Why can an LLM give a wrong answer about your college rules?
**Answer:** Because it never saw your college rules during training, so it may guess.

**Q2.** What do the three words in RAG mean?
**Answer:** Retrieval means finding information, Augmented means adding it to the question, and Generation means writing the answer.

**Q3.** What is an embedding?
**Answer:** A list of numbers that shows the meaning of a piece of text.

**Q4.** Does RAG retrain the LLM?
**Answer:** No. RAG only gives the LLM information inside the prompt. The LLM itself does not change.
