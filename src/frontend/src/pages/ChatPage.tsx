import { useState, useRef, useEffect } from 'react';
import { Button } from '../components/ui/button';
import { chatApi, siteApi } from '../api';
import { ChatMessage } from '../components/ChatMessage';
import { ReferenceTab } from '../components/ReferenceTab';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ChatMessageInterface, Reference } from '../types/search';
import readNDJSONStream from 'ndjson-readablestream';

interface Site {
  id: string;
  name: string;
  url: string;
}

function ChatBar({onSend, disabled}: {onSend: (query: string, deepThink: boolean) => void, disabled: boolean}) {
  const [query, setQuery] = useState('');
  const [deepThink, setDeepThink] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !disabled) {
      onSend(query.trim(), deepThink);
      setQuery('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl mx-auto">
      <div className="flex flex-col gap-2">
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入问题..."
            className="flex-1 bg-background border border-input rounded-md px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary/50"
            disabled={disabled}
          />
          <Button type="submit" variant="default" disabled={disabled || !query.trim()}>
            发送
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm flex items-center gap-1 cursor-pointer">
            <input 
              type="checkbox" 
              checked={deepThink} 
              onChange={(e) => setDeepThink(e.target.checked)}
              className="rounded border-gray-300"
            />
            深度思考模式
          </label>
          {disabled && (
            <Button 
              type="button" 
              variant="outline" 
              size="sm" 
              className="ml-auto"
              onClick={() => onSend('', false)}
            >
              取消
            </Button>
          )}
        </div>
      </div>
    </form>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-[60vh] text-center p-8">
      <h2 className="text-2xl font-bold mb-2">开始一段对话</h2>
      <p className="text-muted-foreground mb-8 max-w-md">
        输入您的问题，AI助手将为您提供有参考资料支持的回答
      </p>
    </div>
  );
}

export function ChatPage() {
  const chatMessageStreamEnd = useRef<HTMLDivElement>(null);
  const [messages, setMessages] = useState<ChatMessageInterface[]>([]);
  const [site_id, setSiteId] = useState<string | null>(null);
  const [sites, setSites] = useState<Site[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isSearching, setIsSearching] = useState<string[] | null>(null);
  const [isInvestigating, setIsInvestigating] = useState<string[] | null>(null);
  const [selectedReference, setSelectedReference] = useState<Reference | null>(null);
  const [errorState, setErrorState] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    fetchSites();
  }, []);
  
  const scrollToBottom = () => {
    if (chatMessageStreamEnd.current) {
      chatMessageStreamEnd.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setSelectedReference(null);
    setErrorState(null);
    setIsLoading(false);
    setIsStreaming(false);
    setIsSearching(null);
    setIsInvestigating(null);
  };


  const handleSiteChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSiteId(e.target.value);
  };

  const fetchSites = async () => {
    const sites = await siteApi.getSites();
    setSites(sites.results);
  };

  const handleReferenceClick = (reference: Reference) => {
    setSelectedReference(reference);
  };

  const handleReferenceClose = () => {
    setSelectedReference(null);
  };

  const handleSendMessage = async (question: string, deepThink: boolean) => {
    if (isStreaming || isLoading) {
      // 如果是取消请求
      if (controller.current) {
        controller.current.abort();
        setIsLoading(false);
        setIsStreaming(false);
        return;
      }
      return;
    }
    
    if (!question) return;
    
    // 清除错误状态
    setErrorState(null);
    
    setIsLoading(true);
    
    // 创建用户消息
    const newMessage: ChatMessageInterface = {
      content: [{
        type: "text",
        text: question
      }],
      role: 'user',
      metadata: {
        timestamp: new Date().toLocaleTimeString(),
        deepThink: deepThink
      }
    };

    const chatHistory = messages.map(msg => ({
      role: msg.role,
      content: msg.content
    })).concat([newMessage]);

    // 将消息添加到聊天历史
    setMessages(prev => [...prev, newMessage]);
    setTimeout(() => {
      scrollToBottom();
    }, 100);
    
    try {
      // 创建响应消息占位
      const responseMessage: ChatMessageInterface = {
        content: [{
          type: "text",
          text: ""
        }],
        role: 'assistant',
        metadata: {
          timestamp: new Date().toLocaleTimeString(),
          deepThink: deepThink
        }
      };
      
      setMessages(prev => [...prev, responseMessage]);
      
      // 模拟搜索中状态
      setIsSearching(['相关资料']);
      setTimeout(() => {
        scrollToBottom();
      }, 100);
      
      // 发送请求到API
      const response = await chatApi.chat(question, site_id || undefined, chatHistory);
      if (!response.ok) {
        return;
      }
      if (!response.body) {
        return;
      }
      let responseText = '';
      for await (const chunk of readNDJSONStream(response.body)) {
        console.log(chunk);
        if (chunk.delta) {
            if (chunk.delta.content) {
                responseText += chunk.delta.content;
                setMessages(prev => {
                    const updatedMessages = [...prev];
                    const lastMessage = updatedMessages[updatedMessages.length - 1];
                    lastMessage.content[0].text = responseText;
                    return updatedMessages;
                });
            }
        }
      }
      
      // 更新响应消息
      setMessages(prev => {
        const updatedMessages = [...prev];
        const lastMessage = updatedMessages[updatedMessages.length - 1];
        lastMessage.content[0].text = responseText;
        return updatedMessages;
      });
      
      setIsSearching(null);
      
    } catch (error) {
      console.error('Chat request error:', error);
      setErrorState('请求处理时发生错误');
      
      // 如果是由于取消引起的错误，不显示错误消息
      if (controller.current?.signal.aborted) {
        setMessages(prev => prev.slice(0, -1));
      }
    } finally {
      setIsLoading(false);
      setIsStreaming(false);
      scrollToBottom();
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="max-w-2xl mx-auto mb-8 text-center pt-8">
        <h1 className="text-3xl font-bold mb-4">SiteSearch</h1>
        {/* 站点选择 */}
        <div className="flex flex-col gap-4 mb-4">
          <div className="flex items-center justify-center">
            <span className="text-sm mr-2">选择站点:</span>
            <select
              value={site_id || ''}
              onChange={handleSiteChange}
              disabled={isLoading}
              className="px-3 py-1 text-sm rounded-md bg-card border border-input focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="">所有站点</option>
              {sites.map(site => (
                <option key={site.id} value={site.id}>
                  {site.name}
                </option>
              ))}
            </select>
            {isLoading && <span className="ml-2 text-sm text-muted-foreground">加载中...</span>}
          </div>
        </div>
        
        {/* 显示错误状态 */}
        {errorState && (
          <div className="mt-2 p-2 bg-red-100 text-red-600 rounded-md text-sm">
            {errorState}
          </div>
        )}
      </div>
      
      <div className="flex-1 overflow-y-auto px-4">
        {messages.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="max-w-2xl mx-auto">
            {messages.map((msg, index) => (
              <ChatMessage
                key={index}
                message={msg}
                isSearching={(index === messages.length - 1 && msg.role === 'assistant') ? isSearching : null}
                isInvestigating={(index === messages.length - 1 && msg.role === 'assistant') ? isInvestigating : null}
                isStreaming={index === messages.length - 1 && msg.role === 'assistant' && isStreaming}
                onReferenceClicked={handleReferenceClick}
              />
            ))}
            {isLoading && <LoadingSpinner />}
            <div ref={chatMessageStreamEnd} />
          </div>
        )}
      </div>
      
      <div className="p-4 border-t">
        <ChatBar onSend={handleSendMessage} disabled={isLoading || isStreaming} />
      </div>
      
      {selectedReference && (
        <ReferenceTab
          reference={selectedReference}
          onClose={handleReferenceClose}
        />
      )}
      
      {messages.length > 0 && (
        <div className="fixed bottom-20 right-4 flex gap-2">
          <Button 
            variant="outline" 
            size="sm" 
            onClick={handleNewChat}
          >
            新对话
          </Button>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => setMessages([])}
          >
            清除聊天
          </Button>
        </div>
      )}
    </div>
  );
} 